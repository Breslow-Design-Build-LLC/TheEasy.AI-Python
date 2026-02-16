"""V2 Gate Orchestrator — single-file, inline-instructions approach.

Uses the OpenAI Responses API with ``instructions`` (inline system prompt)
instead of ``prompt`` (console prompt IDs).  Gate-specific instructions are
defined inline in GATE_DEFS and injected into a master prompt on each call.

V1 endpoints remain untouched — this module powers ``/api/v2/...`` only.
"""

from __future__ import annotations

# ═══════════════════════════════════════════════════════════════════════
# Section 1 — Imports & Constants
# ═══════════════════════════════════════════════════════════════════════

import asyncio
import json
import queue
import threading
from typing import Any, AsyncGenerator, Optional

from ..config import settings
from ..gates.session_state import SessionState
from . import conversation_service as conv_svc
from .display_builder import build_display
from .openai_service import get_client

_MAX_CHAIN_ADVANCES = 10
_MODEL = settings.openai_model
_CHAIN_MODEL = "gpt-4.1-mini"  # faster model for chain-advance calls


# ═══════════════════════════════════════════════════════════════════════
# Section 2 — Gate Definitions (loaded from prompts_export.json)
# ═══════════════════════════════════════════════════════════════════════

import pathlib as _pathlib
import re as _re

_PROMPTS_FILE = _pathlib.Path(__file__).resolve().parent.parent.parent / "prompts_export.json"

# Maps export key → (gate_number, display_name, {placeholder_var: source_key})
_GATE_MAP: dict[str, tuple[int, str, dict[str, str]]] = {
    "gate1":  (1,  "Product Selection",               {"product_options": "product_options"}),
    "gate2":  (2,  "Dimensions & State",               {"dimension_context": "dimension_context"}),
    "gate2b": (19, "Orientation Confirmation",          {"orientation_context": "orientation_context"}),
    "gate3":  (3,  "Bay Logic & Pricing",               {"bay_logic_context": "bay_logic_context"}),
    "gate3b": (20, "Threshold Advisory",                {"threshold_advisory_context": "threshold_advisory_context"}),
    "gate3c": (21, "Dimension Router",                  {"dimension_router_context": "dimension_router_context"}),
    "gate4":  (4,  "Base Pricing",                      {"base_pricing_context": "base_pricing_context"}),
    "gate4b": (22, "Structural Add-Ons Package Rules",  {"structural_addons_context": "structural_addons_context"}),
    "gate5":  (5,  "Color / Finish",                    {"finish_surcharge_context": "finish_surcharge_context"}),
    "gate6":  (6,  "Lighting & Fans",                   {"lighting_fans_context": "lighting_fans_context"}),
    "gate7":  (7,  "Heaters",                           {"heater_context": "heater_context"}),
    "gate8":  (8,  "Shades & Privacy Walls",            {"shades_privacy_context": "shades_privacy_context"}),
    "gate9":  (9,  "Trim & Architectural Upgrades",     {"trim_context": "trim_context"}),
    "gate10": (10, "Electrical Scope",                  {"electrical_scope_context": "electrical_scope_context"}),
    "gate11": (11, "Installation Scope",                {"installation_context": "installation_context"}),
    "gate12": (12, "Design / Engineering / Permits",    {"services_context": "services_context"}),
    "gate13": (13, "Quote Summary",                     {"quote_summary_context": "quote_summary_context"}),
    "gate14": (14, "Internal Line-Item Audit",          {"audit_context": "audit_context"}),
    "gate15": (15, "Final Output Payload",              {"final_payload_context": "final_payload_context"}),
    "gate16": (16, "Detailed Breakdown",                {"breakdown_context": "breakdown_context"}),
    "gate17": (17, "Revisions",                         {"revision_context": "revision_context"}),
    "gate18": (18, "Post-Quote Handoff & Finalize",     {"handoff_context": "handoff_context"}),
}


def _load_gate_defs() -> dict[int, dict[str, Any]]:
    """Load gate definitions from prompts_export.json at startup."""
    with open(_PROMPTS_FILE) as f:
        raw = json.load(f)

    defs: dict[int, dict[str, Any]] = {}
    for key, (number, name, variables) in _GATE_MAP.items():
        if key not in raw:
            continue
        instructions = raw[key]["developer_message"]

        # Replace the injection-point {} with {var_name}
        # The export uses a standalone {} surrounded by newlines for the variable slot
        if len(variables) == 1:
            var_name = list(variables.keys())[0]
            # Pattern: \n{}\n  or  \n\n{}\n\n  (empty braces as injection point)
            instructions = _re.sub(
                r"(\n\n?)\{\}(\n\n?)",
                r"\1{" + var_name + r"}\2",
                instructions,
                count=1,
            )

        # Gate 1 special case: product options are hardcoded inline in the export.
        # Replace the hardcoded list with the dynamic placeholder.
        if number == 1:
            instructions = _re.sub(
                r"PRODUCT_OPTIONS=.*?(?=\n\n## Rules)",
                "PRODUCT_OPTIONS={product_options}",
                instructions,
                flags=_re.DOTALL,
            )

        defs[number] = {
            "name": name,
            "instructions": instructions,
            "variables": variables,
        }
    return defs


GATE_DEFS: dict[int, dict[str, Any]] = _load_gate_defs()


# (Old stub definitions removed — real prompts loaded from prompts_export.json)

GATE_SEQUENCE_V2: list[int] = [
    1, 2, 19, 3, 20, 21, 4, 22, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18
]


# ═══════════════════════════════════════════════════════════════════════
# Section 3 — System Prompt Builder
# ═══════════════════════════════════════════════════════════════════════

_MASTER_PROMPT = """\
You are the Breslow QuoteApp AI — a precise, friendly quoting assistant for \
Breslow Home Products, a premium manufacturer and installer of outdoor living \
structures.

## PRODUCTS
- **R-Blade**: Motorized louvered pergola (bays 8–16 ft wide × 8–23 ft long)
- **R-Shade**: Fixed-roof insulated pergola (bays 8–16 ft wide × 8–23 ft long)
- **R-Breeze**: Screen room / enclosure (bays 4–23 ft wide × 4–23 ft long)
- **K-Bana**: Cabana (limited availability)

## QUOTING PROCESS
You guide the customer through a sequential gate-based flow. Each gate \
collects specific information or computes pricing. You MUST stay within the \
scope of the current gate — never skip ahead, never revisit a completed gate \
unless a revision is routed back.

## RESPONSE FORMAT — STRICT JSON ONLY
Every response MUST be a single valid JSON object. No markdown fences, no \
prose outside the object. Required top-level keys:

  "status"    — "ok" when all required data for this gate is collected and \
validated; "needs_info" when you still need input from the customer.
  "question"  — (string) your message to the customer. Use a friendly, \
professional, concise tone. When status is "ok" this may be a brief \
confirmation or summary of what was decided.
  "warnings"  — (array of strings) any warnings or edge-case notes; empty \
array [] if none.
  + all data fields required by the current gate's instructions.

When a gate returns status "ok", include every computed field the gate \
instructions specify (totals, line items, SKUs, etc.). Omitting required \
output fields will break downstream gates.

## PRICING RULES — ZERO TOLERANCE FOR ERRORS
- Use ONLY prices, SKUs, and formulas provided in the gate context data. \
NEVER invent, estimate, round, or interpolate prices.
- Pricing units must be applied exactly: "per_bay" × total_bays, "percent" \
× base_system_total ÷ 100, "per_sq_ft" × (bay_width_ft × bay_length_ft × \
total_bays), "per_linear_ft" × perimeter or relevant length, "each" × qty, \
"unit" × qty.
- If a size combination is not found in the pricing table, set status to \
"needs_info" and ask the customer to adjust — do NOT approximate.
- Always show your math: unit_price × qty = subtotal for every line item.

## COMPARISON MODE
Some quotes run in comparison_mode (two orientation options: "keep" vs \
"swap"). When comparison_mode is true:
- Compute ALL pricing for BOTH options (result_keep AND result_swap).
- Never merge or average the two — keep them fully separate.
- Downstream gates receive both options and must price each independently.

## MULTI-BAY LOGIC
- Dimensions that exceed a single bay's max width or length are split into \
multiple bays using even-split logic.
- Bay count = ceil(dimension / max_single_bay_dimension).
- Per-bay accessories (lights, heaters, shades) scale with total_bays.

## INTERACTION STYLE
- Be warm, professional, and concise. No filler, no over-explaining.
- Ask one clear question at a time when possible.
- When the customer provides valid data, confirm it and move on (status "ok").
- If input is ambiguous or incomplete, ask a targeted clarifying question \
(status "needs_info").
- Present options with prices when the gate context provides them.
- Never pressure the customer — let them decide at their own pace.
"""


def _build_system_prompt(gate_number: int, session: SessionState) -> str:
    """Assemble the full system prompt: master + gate context + gate instructions."""
    gate_def = GATE_DEFS[gate_number]

    # Resolve variables
    resolved_instructions = gate_def["instructions"]
    for var_name, source_key in gate_def.get("variables", {}).items():
        value = ""
        if hasattr(settings, source_key):
            value = str(getattr(settings, source_key))
        elif source_key in session.product_config:
            value = str(session.product_config[source_key])
        placeholder = "{" + var_name + "}"
        resolved_instructions = resolved_instructions.replace(placeholder, value)

    # Build collected-data summary
    collected = json.dumps(session.product_config, default=str) if session.product_config else "{}"

    return (
        f"{_MASTER_PROMPT}\n"
        f"--- CURRENT GATE: {gate_number} — {gate_def['name']} ---\n\n"
        f"Collected data so far:\n{collected}\n\n"
        f"Gate Instructions:\n{resolved_instructions}"
    )


# ═══════════════════════════════════════════════════════════════════════
# Section 4 — Responses API Client
# ═══════════════════════════════════════════════════════════════════════


_JSON_HINT_MSG = {"role": "developer", "content": "Respond with valid JSON only."}

_CHAIN_EVAL_MSG = {
    "role": "user",
    "content": (
        "Auto-evaluate this gate. Based on the collected data and context in the "
        "system prompt, determine if this gate can be completed automatically or "
        "requires user input. If user choices are needed (selecting options, "
        "confirming preferences, providing information like state/location), return "
        "status: needs_info with clear questions. If all required data is already "
        "available in the collected data, compute results and return status: ok."
    ),
}


def _call_sync(system_prompt: str, messages: list[dict[str, str]], model: str = _MODEL) -> str:
    """Synchronous Responses API call with JSON mode. Returns output text."""
    client = get_client()
    response = client.responses.create(
        model=model,
        instructions=system_prompt,
        input=[_JSON_HINT_MSG] + messages,
        text={"format": {"type": "json_object"}},
        stream=False,
        store=True,
    )
    return response.output_text


async def call_api(system_prompt: str, messages: list[dict[str, str]], model: str = _MODEL) -> str:
    """Async wrapper: run the sync Responses API call in a thread executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _call_sync, system_prompt, messages, model)


def _stream_sync(system_prompt: str, messages: list[dict[str, str]]):
    """Synchronous generator that yields text deltas from streaming."""
    client = get_client()
    stream = client.responses.create(
        model=_MODEL,
        instructions=system_prompt,
        input=[_JSON_HINT_MSG] + messages,
        text={"format": {"type": "json_object"}},
        stream=True,
    )
    for event in stream:
        if event.type == "response.output_text.delta":
            yield event.delta


async def stream_api(
    system_prompt: str, messages: list[dict[str, str]]
) -> AsyncGenerator[str, None]:
    """Async generator that yields text deltas via thread+queue bridge."""
    q: queue.Queue[str | None] = queue.Queue()

    def _producer():
        try:
            for delta in _stream_sync(system_prompt, messages):
                q.put(delta)
        finally:
            q.put(None)

    thread = threading.Thread(target=_producer, daemon=True)
    thread.start()

    loop = asyncio.get_event_loop()
    while True:
        item = await loop.run_in_executor(None, q.get)
        if item is None:
            break
        yield item


# ═══════════════════════════════════════════════════════════════════════
# Section 5 — OrchestratorV2 Class
# ═══════════════════════════════════════════════════════════════════════


def _parse_response_text(text: str) -> dict[str, Any] | None:
    """Try to parse the response as JSON; return None if it's plain text."""
    text = text.strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


class OrchestratorV2:
    """V2 gate orchestrator — inline instructions, Responses API."""

    # ── Session helpers (delegate to conv_svc) ──────────────────────

    async def load_session(self, conversation_id: str) -> SessionState:
        data = await conv_svc.get_session_state(conversation_id)
        return SessionState.from_dict(data)

    async def save_session(self, conversation_id: str, session: SessionState) -> None:
        await conv_svc.update_session_state(conversation_id, session.to_dict())

    # ── Advancement logic ───────────────────────────────────────────

    def should_advance(self, parsed: Optional[dict[str, Any]]) -> bool:
        if not parsed or not isinstance(parsed, dict):
            return False
        status = parsed.get("status", "").lower()
        if status in ("ok", "complete", "done"):
            return True
        if parsed.get("product_id") and not parsed.get("question"):
            return True
        return False

    def collect_data(
        self, session: SessionState, gate_number: int, parsed: dict[str, Any]
    ) -> None:
        """Store relevant fields from a gate response into session.product_config."""
        skip_keys = {"status", "question", "questions", "warnings"}
        for key, value in parsed.items():
            if key not in skip_keys and value is not None:
                session.product_config[key] = value
        # Flatten result_single
        result_single = parsed.get("result_single")
        if isinstance(result_single, dict):
            for k, v in result_single.items():
                if v is not None:
                    session.product_config[k] = v
        # Store full response keyed by gate number
        gate_key = f"gate_{gate_number}_response"
        session.product_config[gate_key] = json.dumps(parsed)
        # Build composite contexts
        self._build_composite_contexts(session)

    def _build_composite_contexts(self, session: SessionState) -> None:
        """Delegate to V1 orchestrator's comprehensive context builders.

        V1's _build_composite_contexts builds properly structured, per-gate
        context objects (orientation_context, base_pricing_context,
        finish_surcharge_context, heater_context, etc.) — all 18 context
        variables that downstream gates expect.

        We reuse it here so V2 gates get the same clean, typed context
        instead of a raw quote_context dump.
        """
        from .orchestrator import GateOrchestrator
        GateOrchestrator._build_composite_contexts(self, session)

    # ── Conditional gate skipping ──────────────────────────────────

    def should_skip_gate(self, gate_number: int, session: SessionState) -> bool:
        """Check if a conditional gate should be skipped based on session state."""
        pc = session.product_config

        # Gate 19 (2b - Orientation): skip if orientation review NOT required
        if gate_number == 19:
            return pc.get("orientation_review_required") is not True

        # Gate 20 (3b - Threshold): skip unless dimensions are near single-bay limits
        if gate_number == 20:
            total_bays = pc.get("total_bays")
            if total_bays is None or total_bays <= 1:
                return True
            dim_rules = json.loads(settings.dimension_context)
            product_id = pc.get("product_id", "r_blade")
            rules = dim_rules.get("DIMENSION_RULES", {}).get(product_id, {})
            max_w = rules.get("max_width_single_bay_ft", 16)
            max_l = rules.get("max_length_single_bay_ft", 23)
            w = pc.get("width_ft_confirmed") or pc.get("width_ft_assumed")
            l_val = pc.get("length_ft_confirmed") or pc.get("length_ft_assumed")
            if w is None or l_val is None:
                return True
            w_over = (w - max_w) if w > max_w else 0
            l_over = (l_val - max_l) if l_val > max_l else 0
            return not (0 < w_over <= 1 or 0 < l_over <= 1)

        # Gate 21 (3c - Dimension Router): only needed after Gate 20 triggered
        if gate_number == 21:
            return pc.get("advisory_triggered") is not True

        # Gate 22 (4b - Structural Add-Ons): skip if structure_type not set
        if gate_number == 22:
            return pc.get("structure_type") is None

        return False

    # ── Gate advancement ────────────────────────────────────────────

    async def advance_gate(
        self,
        conversation_id: str,
        session: SessionState,
        gate_number: int,
        parsed: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        """Advance to next active gate. Returns new gate number or None.

        Automatically skips conditional gates (19, 20, 21, 22) when their
        trigger conditions are not met.
        """
        if parsed and isinstance(parsed, dict):
            self.collect_data(session, gate_number, parsed)
        nxt = session.advance()

        # Skip conditional gates whose trigger flags are not set
        while nxt is not None and self.should_skip_gate(nxt, session):
            nxt = session.advance()

        await self.save_session(conversation_id, session)
        return nxt

    # ── Single gate call ────────────────────────────────────────────

    async def _call_gate(
        self, conversation_id: str, gate_number: int, session: SessionState,
        model: str = _MODEL,
    ) -> tuple[str, Optional[dict[str, Any]]]:
        """Build prompt, call Responses API with full history, return (raw_text, parsed)."""
        system_prompt = _build_system_prompt(gate_number, session)
        history = await conv_svc.get_conversation_history(conversation_id)
        raw_text = await call_api(system_prompt, history, model=model)
        parsed = _parse_response_text(raw_text)
        return raw_text, parsed

    async def _call_gate_chain(
        self, gate_number: int, session: SessionState,
        model: str = _CHAIN_MODEL,
    ) -> tuple[str, Optional[dict[str, Any]]]:
        """Call a gate during chain-advance with minimal messages (no conversation history).

        Uses a single auto-evaluate message instead of full history. This:
        1. Reduces input tokens → faster API response
        2. Prevents the model from misinterpreting prior conversation answers
        3. The system prompt already contains all collected data and gate context
        """
        system_prompt = _build_system_prompt(gate_number, session)
        messages = [_CHAIN_EVAL_MSG]
        raw_text = await call_api(system_prompt, messages, model=model)
        parsed = _parse_response_text(raw_text)
        return raw_text, parsed

    # ── Chain-advance loop ──────────────────────────────────────────

    async def _auto_fetch_and_chain(
        self,
        conversation_id: str,
        session: SessionState,
        metadata: dict[str, Any],
    ) -> None:
        """Auto-fetch next gate, chain-advancing through gates that return ok.

        Optimizations:
        1. should_skip_gate — skips conditional gates (19/20/21/22) without API call
        2. Minimal messages — no conversation history, just an auto-evaluate prompt
        3. gpt-4.1-mini — faster model for chain-advance calls
        """
        skipped_gates: list[dict[str, Any]] = []

        for _ in range(_MAX_CHAIN_ADVANCES):
            gate_number = session.current_gate
            if gate_number not in GATE_DEFS:
                break

            try:
                # Use chain-optimized call: minimal messages + fast model
                raw_text, parsed = await self._call_gate_chain(
                    gate_number, session,
                )

                if self.should_advance(parsed):
                    skipped_gates.append({
                        "gate_number": gate_number,
                        "gate_name": GATE_DEFS[gate_number]["name"],
                        "status": parsed.get("status") if parsed else None,
                    })
                    new_num = await self.advance_gate(
                        conversation_id, session, gate_number, parsed
                    )
                    metadata["advanced_to_gate"] = new_num
                    if new_num is None:
                        metadata["next_gate"] = {
                            "gate_number": gate_number,
                            "gate_name": GATE_DEFS[gate_number]["name"],
                            "response": parsed or raw_text,
                        }
                        break
                    continue

                # Gate has a question — stop here
                metadata["next_gate"] = {
                    "gate_number": gate_number,
                    "gate_name": GATE_DEFS[gate_number]["name"],
                    "response": parsed or raw_text,
                }
                break

            except Exception as e:
                metadata["next_gate_error"] = str(e)
                break

        if skipped_gates:
            metadata["skipped_gates"] = skipped_gates

    # ── Main entry points ───────────────────────────────────────────

    async def handle_message(
        self, conversation_id: str, user_message: str
    ) -> dict[str, Any]:
        """Process a user message (non-streaming): store, call gate, advance, return."""
        await conv_svc.add_message(conversation_id, "user", user_message)

        session = await self.load_session(conversation_id)
        gate_number = session.current_gate

        if gate_number not in GATE_DEFS:
            raise ValueError(f"Unknown gate {gate_number}")

        raw_text, parsed = await self._call_gate(conversation_id, gate_number, session)

        metadata: dict[str, Any] = {
            "gate_number": gate_number,
            "gate_name": GATE_DEFS[gate_number]["name"],
            "api_version": "v2",
        }
        if parsed and isinstance(parsed, dict):
            metadata["parsed_status"] = parsed.get("status")

        if self.should_advance(parsed):
            new_gate_num = await self.advance_gate(
                conversation_id, session, gate_number, parsed
            )
            metadata["advanced_to_gate"] = new_gate_num

            if new_gate_num is not None:
                await self._auto_fetch_and_chain(conversation_id, session, metadata)
        else:
            await self.save_session(conversation_id, session)

        display = build_display(
            parsed=parsed,
            raw_text=raw_text,
            metadata=metadata,
            gate_number=gate_number,
            gate_name=GATE_DEFS[gate_number]["name"],
        )

        msg = await conv_svc.add_message(
            conversation_id,
            "assistant",
            raw_text,
            response_json=parsed,
            metadata_json=metadata,
        )
        msg["display"] = display
        return msg

    async def handle_message_stream(
        self, conversation_id: str, user_message: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Streaming version: yields dicts with type='chunk' or type='done'."""
        await conv_svc.add_message(conversation_id, "user", user_message)

        session = await self.load_session(conversation_id)
        gate_number = session.current_gate

        if gate_number not in GATE_DEFS:
            raise ValueError(f"Unknown gate {gate_number}")

        system_prompt = _build_system_prompt(gate_number, session)
        history = await conv_svc.get_conversation_history(conversation_id)

        chunks: list[str] = []
        async for delta in stream_api(system_prompt, history):
            chunks.append(delta)
            yield {"type": "chunk", "delta": delta}

        full_text = "".join(chunks).strip()
        parsed = _parse_response_text(full_text)

        metadata: dict[str, Any] = {
            "gate_number": gate_number,
            "gate_name": GATE_DEFS[gate_number]["name"],
            "api_version": "v2",
        }
        if parsed and isinstance(parsed, dict):
            metadata["parsed_status"] = parsed.get("status")

        if self.should_advance(parsed):
            new_gate_num = await self.advance_gate(
                conversation_id, session, gate_number, parsed
            )
            metadata["advanced_to_gate"] = new_gate_num

            if new_gate_num is not None:
                await self._auto_fetch_and_chain(conversation_id, session, metadata)
        else:
            await self.save_session(conversation_id, session)

        display = build_display(
            parsed=parsed,
            raw_text=full_text,
            metadata=metadata,
            gate_number=gate_number,
            gate_name=GATE_DEFS[gate_number]["name"],
        )

        msg = await conv_svc.add_message(
            conversation_id,
            "assistant",
            full_text,
            response_json=parsed,
            metadata_json=metadata,
        )
        msg["display"] = display
        yield {"type": "done", "message": msg}


# Module-level singleton
orchestrator_v2 = OrchestratorV2()
