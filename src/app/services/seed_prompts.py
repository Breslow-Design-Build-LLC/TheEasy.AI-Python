"""Seed the Supabase `prompts` table from prompts_export.json + master prompt.

Run once:  python -m src.app.services.seed_prompts
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

# Add project root to path
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.app.services.supabase_service import _service_client

# ── Paths ─────────────────────────────────────────────────────────────────────

_PROMPTS_FILE = pathlib.Path(__file__).resolve().parent.parent.parent / "prompts_export.json"

# ── Gate map (same as orchestrator_v2.py) ──────────────────────────────────────

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

# ── Master prompt (from orchestrator_v2.py) ────────────────────────────────────

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


def seed():
    """Insert master prompt + all gate prompts into Supabase."""
    client = _service_client()

    # Check if already seeded
    existing = client.table("prompts").select("id").limit(1).execute()
    if existing.data:
        print(f"Prompts table already has {len(existing.data)} rows. Skipping seed.")
        print("To re-seed, truncate the prompts table first.")
        return

    # 1. Insert master prompt
    client.table("prompts").insert({
        "prompt_type": "master",
        "gate_number": None,
        "agent_slug": None,
        "version": 1,
        "is_active": True,
        "name": "Master System Prompt v1",
        "developer_message": _MASTER_PROMPT,
        "variables_schema": None,
        "model_override_id": None,
        "notes": "Initial master prompt — shared across all gates",
        "created_by": "seed_script",
    }).execute()
    print("Inserted: Master System Prompt")

    # 2. Load prompts_export.json
    with open(_PROMPTS_FILE) as f:
        raw = json.load(f)

    # 3. Insert each gate prompt
    count = 0
    for key, (gate_number, name, variables) in _GATE_MAP.items():
        if key not in raw:
            print(f"  SKIP: {key} not found in prompts_export.json")
            continue

        instructions = raw[key]["developer_message"]

        # Replace {} injection points with {var_name} placeholders
        if len(variables) == 1:
            var_name = list(variables.keys())[0]
            instructions = re.sub(
                r"(\n\n?)\{\}(\n\n?)",
                r"\1{" + var_name + r"}\2",
                instructions,
                count=1,
            )

        # Gate 1 special case: replace hardcoded product options with placeholder
        if gate_number == 1:
            instructions = re.sub(
                r"PRODUCT_OPTIONS=.*?(?=\n\n## Rules)",
                "PRODUCT_OPTIONS={product_options}",
                instructions,
                flags=re.DOTALL,
            )

        # Build variables schema
        var_schema = {
            var_name: {"type": "string", "source": source_key}
            for var_name, source_key in variables.items()
        }

        client.table("prompts").insert({
            "prompt_type": "gate",
            "gate_number": gate_number,
            "agent_slug": None,
            "version": 1,
            "is_active": True,
            "name": f"Gate {gate_number} — {name} v1",
            "developer_message": instructions,
            "variables_schema": var_schema,
            "model_override_id": None,
            "notes": f"Initial import from prompts_export.json ({key})",
            "created_by": "seed_script",
        }).execute()
        count += 1
        print(f"  Inserted: Gate {gate_number} — {name}")

    print(f"\nDone. Inserted 1 master + {count} gate prompts.")


if __name__ == "__main__":
    seed()
