"""Supervisor Agent — orchestration, routing, and decision-making.

The Supervisor decides:
  - Whether to process the current gate
  - Whether to skip a conditional gate
  - Whether to auto-advance (chain-advance)
  - Where to route revisions (back to a specific gate)

Every decision is logged to the agent_decisions audit table.
"""

from __future__ import annotations

import json
from typing import Any

from ..gates.session_state import SessionState
from ..services import supabase_service as supa


# ═══════════════════════════════════════════════════════════════════════════════
# Gate Skip Logic (deterministic — no LLM needed)
# ═══════════════════════════════════════════════════════════════════════════════

def should_skip_gate(gate_number: int, session: SessionState) -> bool:
    """Determine if a conditional gate should be skipped.

    This is deterministic logic — same as V1/V2 orchestrators.
    Conditional gates: 19 (S02b), 20 (S03b), 21 (S03c), 22 (S04b).
    """
    config = session.product_config

    if gate_number == 19:  # Orientation Confirmation
        return not config.get("orientation_review_required", False)

    if gate_number == 20:  # Threshold Advisory
        return not config.get("threshold_triggered", False)

    if gate_number == 21:  # Dimension Router
        return not config.get("dimension_router_needed", False)

    if gate_number == 22:  # Structural Add-Ons
        total_bays = config.get("total_bays", 1)
        if isinstance(total_bays, dict):
            # Comparison mode
            keep_bays = total_bays.get("keep", 1)
            swap_bays = total_bays.get("swap", 1)
            return keep_bays <= 1 and swap_bays <= 1
        return total_bays <= 1

    return False


def should_advance(parsed_response: dict[str, Any]) -> bool:
    """Check if a gate response indicates completion (status ok/complete/done)."""
    status = str(parsed_response.get("status", "")).lower().strip()
    return status in ("ok", "complete", "done")


# ═══════════════════════════════════════════════════════════════════════════════
# Decision Logging
# ═══════════════════════════════════════════════════════════════════════════════

def log_decision(
    conversation_id: str,
    gate_number: int,
    action: str,
    reasoning: str,
    target_gate: int | None = None,
    confidence: float | None = None,
    session: SessionState | None = None,
    input_summary: str | None = None,
) -> None:
    """Log a Supervisor decision to the audit table."""
    try:
        snapshot = None
        if session:
            snapshot = {
                "current_gate": session.current_gate,
                "product_config_keys": list(session.product_config.keys()),
            }

        supa.log_agent_decision(
            conversation_id=conversation_id,
            gate_number=gate_number,
            agent_slug="supervisor",
            action=action,
            reasoning=reasoning,
            target_gate=target_gate,
            confidence=confidence,
            input_summary=input_summary,
            session_snapshot=snapshot,
        )
    except Exception:
        pass  # Audit failures never break the flow


# ═══════════════════════════════════════════════════════════════════════════════
# Data Collection (extract gate output into session state)
# ═══════════════════════════════════════════════════════════════════════════════

def collect_data(
    gate_number: int,
    parsed_response: dict[str, Any],
    session: SessionState,
) -> None:
    """Extract relevant data from a gate response into session.product_config.

    This replicates the V1/V2 collect_data logic — each gate's output
    fields are stored so downstream gates can reference them.
    """
    config = session.product_config

    if gate_number == 1:  # Product Selection
        config["product_id"] = parsed_response.get("product_id")
        config["product_label"] = parsed_response.get("product_label")

    elif gate_number == 2:  # Dimensions
        for key in [
            "dim_a_raw", "dim_b_raw",
            "dim_a_ft_decimal", "dim_b_ft_decimal",
            "dim_a_ft_rounded", "dim_b_ft_rounded",
            "width_ft_assumed", "length_ft_assumed",
            "bay_count_as_entered", "bay_count_swapped",
            "orientation_review_required", "orientation_review_reasons",
        ]:
            if key in parsed_response:
                config[key] = parsed_response[key]

    elif gate_number == 19:  # Orientation Confirmation
        for key in [
            "orientation_choice", "comparison_mode",
            "width_ft_confirmed", "length_ft_confirmed",
            "option_keep", "option_swap",
        ]:
            if key in parsed_response:
                config[key] = parsed_response[key]

    elif gate_number == 3:  # Bay Logic
        for key in [
            "total_bays", "bay_width_ft", "bay_length_ft",
            "bays", "base_system_total", "structural_items",
        ]:
            if key in parsed_response:
                config[key] = parsed_response[key]
        # Store as context for downstream
        config["bay_logic_result"] = parsed_response

    elif gate_number == 4:  # Base Pricing
        for key in [
            "sku", "unit_price", "base_subtotal",
            "result_single", "result_keep", "result_swap",
        ]:
            if key in parsed_response:
                config[key] = parsed_response[key]
        config["base_pricing_result"] = parsed_response

    elif gate_number == 22:  # Structural Add-Ons
        config["structural_addons_result"] = parsed_response

    elif gate_number == 5:  # Color/Finish
        config["color_finish_result"] = parsed_response

    elif gate_number == 6:  # Lighting/Fans
        config["lighting_fans_result"] = parsed_response

    elif gate_number == 7:  # Heaters
        config["heater_result"] = parsed_response

    elif gate_number == 8:  # Shades/Privacy
        config["shades_privacy_result"] = parsed_response

    elif gate_number == 9:  # Trim
        config["trim_result"] = parsed_response

    elif gate_number == 10:  # Electrical
        config["electrical_result"] = parsed_response

    elif gate_number == 11:  # Installation
        config["installation_result"] = parsed_response

    elif gate_number == 12:  # Services
        config["services_result"] = parsed_response

    elif gate_number == 13:  # Quote Summary
        config["quote_summary"] = parsed_response

    elif gate_number == 14:  # Audit
        config["audit_result"] = parsed_response

    elif gate_number == 15:  # Final Payload
        config["final_payload"] = parsed_response

    elif gate_number == 16:  # Breakdown
        config["breakdown"] = parsed_response

    elif gate_number == 17:  # Revisions
        config["revision_result"] = parsed_response

    elif gate_number == 18:  # Handoff
        config["handoff_result"] = parsed_response
