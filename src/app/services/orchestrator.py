"""Gate orchestrator: resolves which gate/prompt to use and manages advancement."""

from __future__ import annotations

from typing import Any, Optional

from ..config import settings
from ..gates.models import GateConfig, GateStatus
from ..gates.registry import get_gate
from ..gates.session_state import SessionState
from . import conversation_service as conv_svc


class GateOrchestrator:
    """Stateless helper that loads/saves session state and resolves gates."""

    async def load_session(self, conversation_id: str) -> SessionState:
        data = await conv_svc.get_session_state(conversation_id)
        return SessionState.from_dict(data)

    async def save_session(self, conversation_id: str, session: SessionState) -> None:
        await conv_svc.update_session_state(conversation_id, session.to_dict())

    async def resolve_gate(self, conversation_id: str) -> tuple[GateConfig, SessionState]:
        """Load session and return the current gate config (replaces _pick_prompt)."""
        session = await self.load_session(conversation_id)
        gate = get_gate(session.current_gate)

        # If current gate is a placeholder, try to advance to next active gate
        if gate.status == GateStatus.PLACEHOLDER:
            nxt = session.advance()
            if nxt is not None:
                gate = get_gate(nxt)
                await self.save_session(conversation_id, session)

        return gate, session

    def resolve_variables(self, gate: GateConfig, session: SessionState) -> dict[str, str]:
        """Map the gate's variables_template to actual values."""
        var_map: dict[str, str] = {}
        for var_name, source_key in gate.variables_template.items():
            # Check settings first, then session product_config
            if hasattr(settings, source_key):
                var_map[var_name] = getattr(settings, source_key)
            elif source_key in session.product_config:
                var_map[var_name] = str(session.product_config[source_key])
            else:
                var_map[var_name] = ""
        return var_map

    def should_advance(self, parsed: Optional[dict[str, Any]]) -> bool:
        """Decide whether the conversation should advance to the next gate."""
        if not parsed or not isinstance(parsed, dict):
            return False
        status = parsed.get("status", "").lower()
        return status in ("ok", "complete", "done")

    async def advance_gate(
        self, conversation_id: str, session: SessionState
    ) -> Optional[int]:
        """Advance to the next active gate and persist. Returns new gate number or None."""
        nxt = session.advance()
        await self.save_session(conversation_id, session)
        return nxt


orchestrator = GateOrchestrator()
