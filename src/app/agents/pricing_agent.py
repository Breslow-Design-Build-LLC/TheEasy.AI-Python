"""Pricing Agent — deterministic Python sandbox, NOT an LLM.

Law #1: Numbers are Never Generated — Only Retrieved and Calculated.

This agent calls pricing_loader.py functions to retrieve pricing data from
Supabase, performs calculations, and returns structured results. It NEVER
calls an LLM. Hallucinated prices are architecturally impossible.

Every calculation is logged to the pricing_traces audit table.
"""

from __future__ import annotations

import json
from typing import Any

from ..gates.session_state import SessionState
from ..services import pricing_loader
from ..services import supabase_service as supa


def execute(
    gate_number: int,
    session: SessionState,
    conversation_id: str | None = None,
) -> dict[str, Any] | None:
    """Execute pricing calculations for a gate.

    Returns:
        dict with pricing data, or None if this gate doesn't need pricing.
    """
    product_id = session.product_config.get("product_id", "")

    # Route to gate-specific pricing logic
    handler = _GATE_HANDLERS.get(gate_number)
    if handler is None:
        return None

    result = handler(session, product_id)

    # Log to audit if conversation_id provided
    if conversation_id and result:
        _log_traces(conversation_id, gate_number, product_id, result)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Gate-specific pricing handlers
# ═══════════════════════════════════════════════════════════════════════════════

def _price_bay_logic(session: SessionState, product_id: str) -> dict[str, Any]:
    """Gate 3: Bay Logic — calculate bay splits and structural implications."""
    config = session.product_config
    width = config.get("width_ft_assumed") or config.get("width_ft_confirmed")
    length = config.get("length_ft_assumed") or config.get("length_ft_confirmed")

    if not width or not length:
        return {"error": "Missing dimensions"}

    # Get structural items for multi-bay builds
    structural = pricing_loader.get_structural_items()
    multibay = pricing_loader.get_multibay_addons()

    return {
        "operation": "bay_logic",
        "structural_items": structural,
        "multibay_addons": multibay,
    }


def _price_base(session: SessionState, product_id: str) -> dict[str, Any]:
    """Gate 4: Base Pricing — look up unit price from product table."""
    table = pricing_loader.get_base_pricing_table(product_id)
    return {
        "operation": "base_price_lookup",
        "pricing_table": table,
    }


def _price_structural_addons(session: SessionState, product_id: str) -> dict[str, Any]:
    """Gate 22: Structural Add-Ons — posts, beams, headers for multi-bay."""
    structural = pricing_loader.get_structural_items()
    multibay = pricing_loader.get_multibay_addons()
    return {
        "operation": "structural_addons",
        "structural_items": structural,
        "multibay_addons": multibay,
    }


def _price_color_finish(session: SessionState, product_id: str) -> dict[str, Any]:
    """Gate 5: Color/Finish surcharges."""
    surcharges = pricing_loader.get_color_surcharges(product_id)
    return {
        "operation": "color_surcharge",
        "surcharge_options": surcharges,
    }


def _price_lighting_fans(session: SessionState, product_id: str) -> dict[str, Any]:
    """Gate 6: Lighting & Fan items."""
    items = pricing_loader.get_lighting_fans(product_id)
    return {
        "operation": "lighting_fans",
        "menu_items": items,
    }


def _price_heaters(session: SessionState, product_id: str) -> dict[str, Any]:
    """Gate 7: Heater models, beams, and controls."""
    items = pricing_loader.get_heater_items()
    return {
        "operation": "heaters",
        "menu_items": items,
    }


def _price_shades_privacy(session: SessionState, product_id: str) -> dict[str, Any]:
    """Gate 8: Shades & Privacy Walls."""
    shade_table = pricing_loader.get_shade_pricing_table()
    shade_install = pricing_loader.get_shade_install_price()
    privacy_pricing = pricing_loader.get_privacy_wall_pricing()
    privacy_surcharges = pricing_loader.get_privacy_wall_surcharges()
    return {
        "operation": "shades_privacy",
        "shade_pricing_table": shade_table,
        "shade_install_price": shade_install,
        "privacy_wall_pricing": privacy_pricing,
        "privacy_wall_surcharges": privacy_surcharges,
    }


def _price_trim(session: SessionState, product_id: str) -> dict[str, Any]:
    """Gate 9: Trim & Architectural upgrades."""
    items = pricing_loader.get_trim_items(product_id)
    return {
        "operation": "trim_architectural",
        "menu_items": items,
    }


def _price_electrical(session: SessionState, product_id: str) -> dict[str, Any]:
    """Gate 10: Electrical scope items."""
    items = pricing_loader.get_electrical_items()
    return {
        "operation": "electrical",
        "menu_items": items,
    }


def _price_quote_summary(session: SessionState, product_id: str) -> dict[str, Any]:
    """Gate 13: Quote Summary — compile all line items."""
    return {
        "operation": "quote_summary",
        "product_config": session.product_config,
    }


# ── Handler dispatch table ────────────────────────────────────────────────────

_GATE_HANDLERS: dict[int, Any] = {
    3:  _price_bay_logic,
    4:  _price_base,
    22: _price_structural_addons,
    5:  _price_color_finish,
    6:  _price_lighting_fans,
    7:  _price_heaters,
    8:  _price_shades_privacy,
    9:  _price_trim,
    10: _price_electrical,
    13: _price_quote_summary,
}


# ═══════════════════════════════════════════════════════════════════════════════
# Audit Logging
# ═══════════════════════════════════════════════════════════════════════════════

def _log_traces(
    conversation_id: str,
    gate_number: int,
    product_id: str,
    result: dict[str, Any],
) -> None:
    """Log pricing calculations to the pricing_traces audit table."""
    try:
        operation = result.get("operation", "unknown")
        # Build a human-readable math trace
        item_count = 0
        for key, val in result.items():
            if isinstance(val, list):
                item_count += len(val)

        math_trace = f"{operation}: {item_count} items loaded for product={product_id}"

        supa.log_pricing_trace(
            conversation_id=conversation_id,
            gate_number=gate_number,
            operation=operation,
            input_data={"product_id": product_id, "gate_number": gate_number},
            output_data=result,
            math_trace=math_trace,
        )
    except Exception:
        pass  # Audit failures should never break the flow
