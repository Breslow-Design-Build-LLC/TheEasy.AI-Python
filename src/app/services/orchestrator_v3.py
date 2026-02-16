"""V3 Orchestrator — multi-agent A.S.C.E.N.D. architecture.

Coordinates 4 agents (Supervisor, Conversation, Pricing, Compliance) to
process each gate. Loads config from Supabase, persists sessions to Supabase,
and logs all decisions to audit tables.

Uses the same response format as V1/V2 for backward compatibility.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Generator

from ..agents import compliance_agent, conversation_agent, pricing_agent, supervisor_agent
from ..config import settings
from ..gates.session_state import SessionState
from ..services import supabase_service as supa
from ..services.display_builder import build_display
from ..services.llm_service import call_llm
from ..services.model_resolver import resolve_chain_model

logger = logging.getLogger(__name__)

_MAX_CHAIN_ADVANCES = 10


class OrchestratorV3:
    """V3 multi-agent orchestrator for the Breslow QuoteApp."""

    # ── Session Management ────────────────────────────────────────────────

    def load_session(self, conversation_id: str) -> SessionState:
        """Load session state from Supabase."""
        state = supa.get_session_state(conversation_id)
        if not state:
            return SessionState()

        session = SessionState()
        session.current_gate = state.get("current_gate", 1)
        session.product_config = state.get("product_config", {})
        session.gate_sequence = supa.get_gate_sequence()
        return session

    def save_session(self, conversation_id: str, session: SessionState) -> None:
        """Persist session state to Supabase."""
        supa.save_session_state(
            conversation_id=conversation_id,
            current_gate=session.current_gate,
            product_config=session.product_config,
            comparison_mode=session.product_config.get("comparison_mode", False),
        )

    # ── Context Building (reuse V1 logic) ─────────────────────────────────

    def _build_composite_contexts(self, session: SessionState) -> None:
        """Build all gate context variables into session.product_config.

        Delegates to V1 orchestrator's proven context-building logic.
        """
        try:
            from .orchestrator import GateOrchestrator
            GateOrchestrator._build_composite_contexts(self, session)
        except Exception as e:
            logger.warning(f"Context build failed, continuing: {e}")

    # ── Gate Advancement ──────────────────────────────────────────────────

    def _next_active_gate(self, session: SessionState) -> int | None:
        """Find the next gate in sequence after current_gate, skipping conditionals."""
        seq = session.gate_sequence
        try:
            idx = seq.index(session.current_gate)
        except ValueError:
            return None

        for next_gate in seq[idx + 1:]:
            if not supervisor_agent.should_skip_gate(next_gate, session):
                return next_gate
        return None

    def _advance_gate(self, conversation_id: str, session: SessionState) -> int | None:
        """Move to the next active gate. Returns the new gate number or None."""
        next_gate = self._next_active_gate(session)
        if next_gate is None:
            return None

        session.current_gate = next_gate
        self.save_session(conversation_id, session)
        return next_gate

    # ── Main Entry Point ──────────────────────────────────────────────────

    def handle_message(
        self,
        conversation_id: str,
        user_message: str,
    ) -> dict[str, Any]:
        """Process a user message through the multi-agent pipeline.

        Returns:
            ExternalAPIResponse-compatible dict with display, gate info, etc.
        """
        # 1. Load session
        session = self.load_session(conversation_id)
        gate_number = session.current_gate

        # 2. Build composite contexts
        self._build_composite_contexts(session)

        # 3. Save user message to Supabase
        supa.add_message(
            conversation_id=conversation_id,
            role="user",
            content=user_message,
            gate_number=gate_number,
        )

        # 4. Get conversation history
        history = supa.get_conversation_history(conversation_id)

        # 5. Get gate config
        gate_config = supa.get_gate(gate_number)
        gate_name = gate_config["name"] if gate_config else f"Gate {gate_number}"

        # 6. Run Pricing Agent (if gate needs it)
        pricing_data = None
        if gate_config and gate_config.get("needs_pricing"):
            pricing_data = pricing_agent.execute(
                gate_number=gate_number,
                session=session,
                conversation_id=conversation_id,
            )

        # 7. Run Conversation Agent
        parsed, llm_resp = conversation_agent.generate_response(
            gate_number=gate_number,
            user_message=user_message,
            session=session,
            conversation_history=history,
            pricing_data=pricing_data,
        )

        # 8. Run Compliance Agent (if gate needs it)
        compliance_result = None
        if gate_config and gate_config.get("needs_compliance"):
            compliance_result = compliance_agent.validate(
                gate_number=gate_number,
                gate_response=parsed,
                session=session,
                pricing_data=pricing_data,
                conversation_id=conversation_id,
            )

        # 9. Log gate result
        status = parsed.get("status", "needs_info")
        try:
            supa.log_gate_result(
                conversation_id=conversation_id,
                gate_number=gate_number,
                status=status,
                result_json=parsed,
                pricing_data=pricing_data,
                model_used=llm_resp.model_used,
                attempt_count=1,
            )
        except Exception:
            pass

        # 10. If status is ok, collect data and advance
        advanced_gates = []
        if supervisor_agent.should_advance(parsed):
            supervisor_agent.collect_data(gate_number, parsed, session)
            supervisor_agent.log_decision(
                conversation_id=conversation_id,
                gate_number=gate_number,
                action="process_gate",
                reasoning=f"Gate {gate_number} completed with status ok",
                session=session,
            )

            # Chain-advance through auto-advance gates
            advanced_gates = self._chain_advance(conversation_id, session)

        # 11. Save session
        self.save_session(conversation_id, session)

        # 12. Save assistant message
        display = build_display(parsed, gate_number, gate_name)
        response_content = json.dumps(display, default=str)

        supa.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=parsed.get("question", response_content),
            gate_number=gate_number,
            response_json=parsed,
            metadata_json={
                "gate_name": gate_name,
                "advanced_gates": advanced_gates,
                "compliance": compliance_result,
            },
            agent_slug="conversation",
            model_used=llm_resp.model_used,
            input_tokens=llm_resp.input_tokens,
            output_tokens=llm_resp.output_tokens,
            latency_ms=llm_resp.latency_ms,
        )

        # 13. Build external response
        return {
            "conversation_id": conversation_id,
            "gate_number": session.current_gate,
            "gate_name": gate_name,
            "response": parsed,
            "display": display,
            "metadata": {
                "model_used": llm_resp.model_used,
                "input_tokens": llm_resp.input_tokens,
                "output_tokens": llm_resp.output_tokens,
                "latency_ms": llm_resp.latency_ms,
                "advanced_gates": advanced_gates,
                "compliance_passed": compliance_result.get("passed") if compliance_result else None,
            },
        }

    # ── Chain-Advance ─────────────────────────────────────────────────────

    def _chain_advance(
        self,
        conversation_id: str,
        session: SessionState,
    ) -> list[int]:
        """Auto-advance through gates that don't need user input.

        Returns list of gate numbers that were auto-advanced.
        """
        advanced = []

        for _ in range(_MAX_CHAIN_ADVANCES):
            next_gate = self._advance_gate(conversation_id, session)
            if next_gate is None:
                break

            gate_config = supa.get_gate(next_gate)
            if not gate_config:
                break

            # Only auto-advance gates marked as auto_advance
            if not gate_config.get("auto_advance"):
                break

            # Rebuild contexts for the new gate
            self._build_composite_contexts(session)

            # Run Pricing Agent if needed
            pricing_data = None
            if gate_config.get("needs_pricing"):
                pricing_data = pricing_agent.execute(
                    gate_number=next_gate,
                    session=session,
                    conversation_id=conversation_id,
                )

            # Call Conversation Agent with chain-advance model (faster)
            chain_model = resolve_chain_model(next_gate)
            parsed, llm_resp = conversation_agent.generate_response(
                gate_number=next_gate,
                user_message="[auto-advance: process this gate with the collected data]",
                session=session,
                pricing_data=pricing_data,
            )

            # Log gate result
            try:
                supa.log_gate_result(
                    conversation_id=conversation_id,
                    gate_number=next_gate,
                    status=parsed.get("status", "needs_info"),
                    result_json=parsed,
                    pricing_data=pricing_data,
                    was_auto_advanced=True,
                    was_chain_advanced=True,
                    model_used=llm_resp.model_used,
                )
            except Exception:
                pass

            if supervisor_agent.should_advance(parsed):
                supervisor_agent.collect_data(next_gate, parsed, session)
                supervisor_agent.log_decision(
                    conversation_id=conversation_id,
                    gate_number=next_gate,
                    action="chain_advance",
                    reasoning=f"Gate {next_gate} auto-advanced with status ok",
                    session=session,
                )
                advanced.append(next_gate)
            else:
                # Gate needs user input — stop chain
                break

        return advanced

    # ── Streaming ─────────────────────────────────────────────────────────

    def handle_message_stream(
        self,
        conversation_id: str,
        user_message: str,
    ) -> Generator[dict[str, Any], None, None]:
        """Stream version of handle_message.

        Yields SSE-compatible event dicts:
          {"event": "chunk", "data": {"delta": "text..."}}
          {"event": "done",  "data": {full response}}
        """
        # For now, call handle_message and yield the result as a single "done" event.
        # True streaming (yielding deltas during LLM call) will be added in a future iteration.
        result = self.handle_message(conversation_id, user_message)

        # Yield the question as a chunk
        question = result.get("response", {}).get("question", "")
        if question:
            yield {"event": "chunk", "data": {"conversation_id": conversation_id, "delta": question}}

        # Yield the done event
        yield {"event": "done", "data": result}
