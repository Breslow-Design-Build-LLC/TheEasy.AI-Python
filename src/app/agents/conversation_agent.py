"""Conversation Agent — generates user-facing responses for each gate.

This is the agent that "talks" to the customer. It loads the gate prompt
from Supabase (or falls back to prompts_export.json), injects context
variables, and calls the LLM to produce a JSON response.

Returns the same shape as V1/V2: {status, question, warnings, ...data fields}
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..config import settings
from ..gates.session_state import SessionState
from ..services import supabase_service as supa
from ..services.llm_service import LLMResponse, call_llm
from ..services.model_resolver import resolve_model

# ── Fallback: load from prompts_export.json if Supabase prompt is a stub ──────

_GATE_DEFS_CACHE: dict[int, dict[str, Any]] | None = None


def _get_file_gate_defs() -> dict[int, dict[str, Any]]:
    """Load gate definitions from prompts_export.json (V2 fallback)."""
    global _GATE_DEFS_CACHE
    if _GATE_DEFS_CACHE is not None:
        return _GATE_DEFS_CACHE

    from ..services.orchestrator_v2 import GATE_DEFS
    _GATE_DEFS_CACHE = GATE_DEFS
    return _GATE_DEFS_CACHE


# ── Gate-to-variable map (which context variable each gate needs) ─────────────

_GATE_VARIABLE_MAP: dict[int, dict[str, str]] = {
    1:  {"product_options": "product_options"},
    2:  {"dimension_context": "dimension_context"},
    19: {"orientation_context": "orientation_context"},
    3:  {"bay_logic_context": "bay_logic_context"},
    20: {"threshold_advisory_context": "threshold_advisory_context"},
    21: {"dimension_router_context": "dimension_router_context"},
    4:  {"base_pricing_context": "base_pricing_context"},
    22: {"structural_addons_context": "structural_addons_context"},
    5:  {"finish_surcharge_context": "finish_surcharge_context"},
    6:  {"lighting_fans_context": "lighting_fans_context"},
    7:  {"heater_context": "heater_context"},
    8:  {"shades_privacy_context": "shades_privacy_context"},
    9:  {"trim_context": "trim_context"},
    10: {"electrical_scope_context": "electrical_scope_context"},
    11: {"installation_context": "installation_context"},
    12: {"services_context": "services_context"},
    13: {"quote_summary_context": "quote_summary_context"},
    14: {"audit_context": "audit_context"},
    15: {"final_payload_context": "final_payload_context"},
    16: {"breakdown_context": "breakdown_context"},
    17: {"revision_context": "revision_context"},
    18: {"handoff_context": "handoff_context"},
}


def _get_gate_instructions(gate_number: int) -> str:
    """Get the developer_message for a gate — Supabase first, file fallback."""
    prompt = supa.get_active_prompt(gate_number=gate_number, prompt_type="gate")
    if prompt:
        text = prompt.get("developer_message", "")
        if text and text != "[LOADED_FROM_FILE]":
            return text

    # Fallback to file-based definitions
    file_defs = _get_file_gate_defs()
    if gate_number in file_defs:
        return file_defs[gate_number]["instructions"]

    return f"Process gate {gate_number}. Return JSON with status, question, warnings."


def _get_master_prompt() -> str:
    """Get the master system prompt — Supabase first, inline fallback."""
    text = supa.get_master_prompt()
    if text:
        return text

    # Fallback to V2 inline master prompt
    from ..services.orchestrator_v2 import _MASTER_PROMPT
    return _MASTER_PROMPT


def _resolve_variables(
    instructions: str,
    gate_number: int,
    session: SessionState,
) -> str:
    """Replace {variable_name} placeholders with actual values."""
    variables = _GATE_VARIABLE_MAP.get(gate_number, {})

    for var_name, source_key in variables.items():
        placeholder = "{" + var_name + "}"
        if placeholder not in instructions:
            continue

        # Try settings first (for product_options, dimension_context)
        if hasattr(settings, source_key):
            value = str(getattr(settings, source_key))
        elif source_key in session.product_config:
            value = str(session.product_config[source_key])
        else:
            value = "{}"

        instructions = instructions.replace(placeholder, value)

    return instructions


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def generate_response(
    gate_number: int,
    user_message: str,
    session: SessionState,
    conversation_history: list[dict[str, str]] | None = None,
    pricing_data: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], LLMResponse]:
    """Generate the Conversation Agent's response for a gate.

    Args:
        gate_number:           Current gate
        user_message:          User's input text
        session:               Current SessionState
        conversation_history:  Prior messages [{role, content}, ...]
        pricing_data:          Output from the Pricing Agent (if applicable)

    Returns:
        Tuple of (parsed_response_dict, LLMResponse metadata)
    """
    # 1. Build system prompt
    master = _get_master_prompt()
    instructions = _get_gate_instructions(gate_number)
    instructions = _resolve_variables(instructions, gate_number, session)

    gate_config = supa.get_gate(gate_number)
    gate_name = gate_config["name"] if gate_config else f"Gate {gate_number}"

    collected = json.dumps(session.product_config, default=str) if session.product_config else "{}"

    system_prompt = (
        f"{master}\n"
        f"--- CURRENT GATE: {gate_number} — {gate_name} ---\n\n"
        f"Collected data so far:\n{collected}\n\n"
    )

    # Inject pricing data if available
    if pricing_data:
        system_prompt += f"Pricing Agent Output:\n{json.dumps(pricing_data, default=str)}\n\n"

    system_prompt += f"Gate Instructions:\n{instructions}"

    # 2. Build messages
    messages = list(conversation_history or [])
    messages.append({"role": "user", "content": user_message})

    # 3. Resolve model
    model_info = resolve_model(gate_number, "conversation")

    # 4. Call LLM
    llm_resp = call_llm(
        model_id=model_info["model_id"],
        provider=model_info["provider"],
        messages=messages,
        system_prompt=system_prompt,
        temperature=model_info.get("temperature", 0.3),
        json_mode=True,
    )

    # 5. Parse JSON response
    try:
        parsed = json.loads(llm_resp.content)
    except json.JSONDecodeError:
        # Try to extract JSON from response
        match = re.search(r"\{[\s\S]*\}", llm_resp.content)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                parsed = {
                    "status": "needs_info",
                    "question": llm_resp.content,
                    "warnings": ["Response was not valid JSON"],
                }
        else:
            parsed = {
                "status": "needs_info",
                "question": llm_resp.content,
                "warnings": ["Response was not valid JSON"],
            }

    return parsed, llm_resp
