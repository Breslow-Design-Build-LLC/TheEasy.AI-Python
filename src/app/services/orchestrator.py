"""Gate orchestrator: resolves which gate/prompt to use and manages advancement."""

from __future__ import annotations

import json
from typing import Any, Optional

from ..config import settings
from ..gates.models import GateConfig, GateStatus
from ..gates.registry import get_gate
from ..gates.session_state import SessionState
from . import conversation_service as conv_svc
from . import pricing_loader


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
        if status in ("ok", "complete", "done"):
            return True
        # Gate 1: product selected and no follow-up question
        if parsed.get("product_id") and not parsed.get("question"):
            return True
        return False

    def collect_data(self, session: SessionState, parsed: dict[str, Any]) -> None:
        """Store relevant fields from a gate response into session.product_config."""
        skip_keys = {"status", "question", "questions", "warnings"}
        for key, value in parsed.items():
            if key not in skip_keys and value is not None:
                session.product_config[key] = value
        # Flatten result_single into top-level keys for downstream gates
        result_single = parsed.get("result_single")
        if isinstance(result_single, dict):
            for k, v in result_single.items():
                if v is not None:
                    session.product_config[k] = v
        # Store full response as JSON string keyed by gate number
        gate_key = f"gate_{session.current_gate}_response"
        session.product_config[gate_key] = json.dumps(parsed)
        # Build composite context variables for downstream gates
        self._build_composite_contexts(session)

    def _build_composite_contexts(self, session: SessionState) -> None:
        """Build composite JSON context variables from collected gate data."""
        pc = session.product_config

        # ── orientation_context — needed by Gate 19 (2b) after Gate 2 completes ──
        # Only built when Gate 2 flags orientation review as required
        if pc.get("orientation_review_required") is True:
            dim_rules = json.loads(settings.dimension_context)
            product_id = pc.get("product_id", "r_blade")
            rules = dim_rules.get("DIMENSION_RULES", {}).get(product_id, {})
            orientation_ctx = {
                "product_id": product_id,
                "allow_comparison_mode": True,
                "input_from_s02_1": {
                    "dim_a_ft_rounded": pc.get("dim_a_ft_rounded"),
                    "dim_b_ft_rounded": pc.get("dim_b_ft_rounded"),
                    "bay_count_as_entered": pc.get("bay_count_as_entered"),
                    "bay_count_swapped": pc.get("bay_count_swapped"),
                    "width_ft_assumed": pc.get("width_ft_assumed"),
                    "length_ft_assumed": pc.get("length_ft_assumed"),
                    "orientation_review_reasons": pc.get("orientation_review_reasons", []),
                },
                "max_bay_width_ft": rules.get("max_width_single_bay_ft", 16),
                "max_bay_length_ft": rules.get("max_length_single_bay_ft", 23),
            }
            pc["orientation_context"] = json.dumps(orientation_ctx)

        # ── bay_logic_context — needed by Gate 3 after Gate 19 (Orientation) completes ──
        # Use confirmed dimensions first, fall back to assumed (Gate 2) or option_keep
        width = (
            pc.get("width_ft_confirmed")
            or pc.get("width_ft_assumed")
            or (pc.get("option_keep", {}).get("width_ft") if isinstance(pc.get("option_keep"), dict) else None)
        )
        length = (
            pc.get("length_ft_confirmed")
            or pc.get("length_ft_assumed")
            or (pc.get("option_keep", {}).get("length_ft") if isinstance(pc.get("option_keep"), dict) else None)
        )

        if width is not None and length is not None:
            dim_rules = json.loads(settings.dimension_context)
            product_id = pc.get("product_id", "r_blade")
            rules = dim_rules.get("DIMENSION_RULES", {}).get(product_id, {})
            max_w = rules.get("max_width_single_bay_ft", 16)
            max_l = rules.get("max_length_single_bay_ft", 23)

            bay_logic = {
                "PRODUCT_ID": product_id,
                "MAX_BAY_WIDTH_FT": max_w,
                "MAX_BAY_LENGTH_FT": max_l,
                "INPUT_DIMENSIONS": {
                    "comparison_mode": pc.get("comparison_mode", False),
                    "width_ft": width,
                    "length_ft": length,
                    "option_keep": pc.get("option_keep", {}),
                    "option_swap": pc.get("option_swap", {}),
                },
            }
            pc["bay_logic_context"] = json.dumps(bay_logic)

        # ── threshold_advisory_context — needed by Gate 20 (3b) after Gate 3 ──
        # Built when Gate 3 completes with bay results that may be near single-bay limits
        if pc.get("total_bays") is not None and width is not None and length is not None:
            dim_rules = json.loads(settings.dimension_context)
            product_id = pc.get("product_id", "r_blade")
            rules = dim_rules.get("DIMENSION_RULES", {}).get(product_id, {})
            max_w = rules.get("max_width_single_bay_ft", 16)
            max_l = rules.get("max_length_single_bay_ft", 23)

            threshold_ctx = {
                "PRODUCT_ID": product_id,
                "INPUT_FROM_S02_1": {
                    "width_ft_assumed": pc.get("width_ft_assumed"),
                    "length_ft_assumed": pc.get("length_ft_assumed"),
                    "dim_a_ft_decimal": pc.get("dim_a_ft_decimal"),
                    "dim_b_ft_decimal": pc.get("dim_b_ft_decimal"),
                    "dim_a_ft_rounded": pc.get("dim_a_ft_rounded"),
                    "dim_b_ft_rounded": pc.get("dim_b_ft_rounded"),
                },
                "INPUT_FROM_S02_2": {
                    "comparison_mode": pc.get("comparison_mode", False),
                    "orientation_choice": pc.get("orientation_choice"),
                    "width_ft_confirmed": pc.get("width_ft_confirmed"),
                    "length_ft_confirmed": pc.get("length_ft_confirmed"),
                },
                "LIMITS": {
                    "max_width_single_bay_ft": max_w,
                    "max_length_single_bay_ft": max_l,
                },
                "TOLERANCE": {
                    "enabled": True,
                    "max_overage_ft": 1,
                },
                "INPUT_FROM_S03": {
                    "total_bays": pc.get("total_bays"),
                    "width_bays": pc.get("width_bays"),
                    "length_bays": pc.get("length_bays"),
                },
            }
            pc["threshold_advisory_context"] = json.dumps(threshold_ctx)

        # ── dimension_router_context — needed by Gate 21 (3c) after Gate 20 (3b) ──
        # Routes the final dimension choice into a clean bay_logic_context for Gate 3 re-run
        if pc.get("total_bays") is not None:
            dim_rules = json.loads(settings.dimension_context)
            product_id = pc.get("product_id", "r_blade")
            rules = dim_rules.get("DIMENSION_RULES", {}).get(product_id, {})
            max_w = rules.get("max_width_single_bay_ft", 16)
            max_l = rules.get("max_length_single_bay_ft", 23)

            router_ctx = {
                "PRODUCT_ID": product_id,
                "MAX_BAY_WIDTH_FT": max_w,
                "MAX_BAY_LENGTH_FT": max_l,
                "FROM_S03_1": {
                    "advisory_triggered": pc.get("advisory_triggered", False),
                    "user_choice": pc.get("user_choice"),
                    "compare_mode": pc.get("compare_mode", False),
                    "adjusted_width_ft": pc.get("adjusted_width_ft"),
                    "adjusted_length_ft": pc.get("adjusted_length_ft"),
                },
                "FROM_S02_2": {
                    "comparison_mode": pc.get("comparison_mode", False),
                    "width_ft_confirmed": pc.get("width_ft_confirmed"),
                    "length_ft_confirmed": pc.get("length_ft_confirmed"),
                    "option_keep": pc.get("option_keep", {}),
                    "option_swap": pc.get("option_swap", {}),
                },
            }
            pc["dimension_router_context"] = json.dumps(router_ctx)

        # ── base_pricing_context — needed by Gate 4 after Gate 3 completes ──
        # Combines Gate 3 bay results + product pricing table + multi-bay add-ons
        # Structure: { product_id, product_rules: { <id>: { pricing_table, addons } }, input_from_s03 }
        product_id = pc.get("product_id", "r_blade")
        gate_3_resp = pc.get("gate_3_response")
        if gate_3_resp:
            try:
                s03_data = json.loads(gate_3_resp) if isinstance(gate_3_resp, str) else gate_3_resp
            except (json.JSONDecodeError, TypeError):
                s03_data = {}

            if s03_data.get("status") == "ok":
                pricing_table = pricing_loader.get_base_pricing_table(product_id)
                raw_addons = pricing_loader.get_multibay_addons()

                # Map multi-bay addons to config-driven format with qty_formula
                addons_with_formula = []
                for addon in raw_addons:
                    sku = addon.get("sku", "")
                    formula = "none"
                    if "BTB" in sku or "beam" in sku.lower():
                        formula = "beam_to_beam_cover"
                    elif "PTG" in sku or "pass" in sku.lower() or "gutter" in sku.lower():
                        formula = "pass_through_gutter"
                    addons_with_formula.append({
                        "sku": sku,
                        "description": addon.get("description", ""),
                        "unit_price": addon.get("unit_price", 0),
                        "pricing_unit": addon.get("pricing_unit", "each"),
                        "qty_formula": formula,
                    })

                base_pricing_ctx = {
                    "product_id": product_id,
                    "product_rules": {
                        product_id: {
                            "pricing_table": pricing_table,
                            "addons": addons_with_formula,
                        }
                    },
                    "input_from_s03": {
                        "comparison_mode": s03_data.get("comparison_mode", False),
                        "result_single": s03_data.get("result_single"),
                        "result_keep": s03_data.get("result_keep"),
                        "result_swap": s03_data.get("result_swap"),
                    },
                }
                pc["base_pricing_context"] = json.dumps(base_pricing_ctx)

        # ── structural_addons_context — needed by Gate 22 (4b) after Gate 4 completes ──
        # Combines Gate 3 bay results + structure_type + structural SKU table + rules
        structure_type = pc.get("structure_type")
        if structure_type and gate_3_resp:
            try:
                s03_data_for_struct = json.loads(gate_3_resp) if isinstance(gate_3_resp, str) else gate_3_resp
            except (json.JSONDecodeError, TypeError):
                s03_data_for_struct = {}

            if s03_data_for_struct.get("status") == "ok":
                structural_items = pricing_loader.get_structural_items()

                structural_addons_ctx = {
                    "product_id": product_id,
                    "structure_input": {
                        "structure_type": structure_type,
                        "span_direction_assumption": pc.get("span_direction_assumption", "width"),
                        "requested_post_strategy": pc.get("requested_post_strategy", "default_min"),
                    },
                    "structural_rules": {
                        "clear_span_limits_ft": {
                            "header_beam_required_over_ft": 23,
                            "header_beam_allowed_up_to_ft": 30,
                        },
                    },
                    "sku_table": structural_items,
                    "input_from_s03": {
                        "comparison_mode": s03_data_for_struct.get("comparison_mode", False),
                        "result_single": s03_data_for_struct.get("result_single"),
                        "result_keep": s03_data_for_struct.get("result_keep"),
                        "result_swap": s03_data_for_struct.get("result_swap"),
                    },
                }
                pc["structural_addons_context"] = json.dumps(structural_addons_ctx)

        # ── finish_surcharge_context — needed by Gate 5 after Gate 4/4b ──
        # Combines color surcharge table + bay results for surcharge math
        color_surcharges = pricing_loader.get_color_surcharges(product_id)
        if color_surcharges and gate_3_resp:
            try:
                s03_for_finish = json.loads(gate_3_resp) if isinstance(gate_3_resp, str) else gate_3_resp
            except (json.JSONDecodeError, TypeError):
                s03_for_finish = {}

            if s03_for_finish.get("status") == "ok":
                # Get base system totals from Gate 4 for percent-based surcharges
                gate_4_resp = pc.get("gate_4_response")
                base_system_total = None
                base_system_total_keep = None
                base_system_total_swap = None
                if gate_4_resp:
                    try:
                        s04_data = json.loads(gate_4_resp) if isinstance(gate_4_resp, str) else gate_4_resp
                        if s04_data.get("comparison_mode") is False:
                            base_system_total = s04_data.get("priced_single", {}).get("base_system_total")
                        else:
                            base_system_total_keep = s04_data.get("priced_keep", {}).get("base_system_total")
                            base_system_total_swap = s04_data.get("priced_swap", {}).get("base_system_total")
                    except (json.JSONDecodeError, TypeError):
                        pass

                finish_ctx = {
                    "product_id": product_id,
                    "surcharge_table": color_surcharges,
                    "input_from_s03": {
                        "comparison_mode": s03_for_finish.get("comparison_mode", False),
                        "result_single": s03_for_finish.get("result_single"),
                        "result_keep": s03_for_finish.get("result_keep"),
                        "result_swap": s03_for_finish.get("result_swap"),
                    },
                    "base_system_total": base_system_total,
                    "base_system_total_keep": base_system_total_keep,
                    "base_system_total_swap": base_system_total_swap,
                }
                pc["finish_surcharge_context"] = json.dumps(finish_ctx)

        # ── lighting_fans_context — needed by Gate 6 ──
        # Combines lighting/fan menu items + bay results
        lighting_items = pricing_loader.get_lighting_fans(product_id)
        if lighting_items and gate_3_resp:
            try:
                s03_for_light = json.loads(gate_3_resp) if isinstance(gate_3_resp, str) else gate_3_resp
            except (json.JSONDecodeError, TypeError):
                s03_for_light = {}

            if s03_for_light.get("status") == "ok":
                # Fan beam items from structural loader (needed for companion rule)
                structural_items = pricing_loader.get_structural_items()
                fan_beams = [s for s in structural_items if "FAN-BEAM" in s.get("sku", "")]

                lighting_ctx = {
                    "product_id": product_id,
                    "menu_items": lighting_items,
                    "fan_beam_options": fan_beams,
                    "rules": {
                        "led_strip_requires_driver": True,
                        "ceiling_fan_requires_fan_beam_if_not_in_package": True,
                        "package_includes_fan_beam": True,
                    },
                    "input_from_s03": {
                        "comparison_mode": s03_for_light.get("comparison_mode", False),
                        "result_single": s03_for_light.get("result_single"),
                        "result_keep": s03_for_light.get("result_keep"),
                        "result_swap": s03_for_light.get("result_swap"),
                    },
                }
                pc["lighting_fans_context"] = json.dumps(lighting_ctx)

        # ── heater_context — needed by Gate 7 ──
        heater_items = pricing_loader.get_heater_items()
        if heater_items and gate_3_resp:
            try:
                s03_for_heat = json.loads(gate_3_resp) if isinstance(gate_3_resp, str) else gate_3_resp
            except (json.JSONDecodeError, TypeError):
                s03_for_heat = {}

            if s03_for_heat.get("status") == "ok":
                # Separate heaters vs beams vs controls
                models = [h for h in heater_items if h["sku"].startswith("HTR-")]
                beams = [h for h in heater_items if h["sku"].startswith("CTRL-AZ")]
                controls = [h for h in heater_items if h["sku"].startswith("CTRL-") and not h["sku"].startswith("CTRL-AZ")]

                heater_ctx = {
                    "product_id": product_id,
                    "models": models,
                    "heater_beams": beams,
                    "controls": controls,
                    "rules": {
                        "recessed_requires_heater_beams": True,
                        "beam_ratio_heaters_per_beam": 2,
                        "control_tiers": [
                            {"max_heaters": 2, "sku_suffix": "2"},
                            {"max_heaters": 4, "sku_suffix": "4"},
                        ],
                    },
                    "input_from_s03": {
                        "comparison_mode": s03_for_heat.get("comparison_mode", False),
                        "result_single": s03_for_heat.get("result_single"),
                        "result_keep": s03_for_heat.get("result_keep"),
                        "result_swap": s03_for_heat.get("result_swap"),
                    },
                }
                pc["heater_context"] = json.dumps(heater_ctx)

        # ── shades_privacy_context — needed by Gate 8 ──
        if gate_3_resp:
            try:
                s03_for_shades = json.loads(gate_3_resp) if isinstance(gate_3_resp, str) else gate_3_resp
            except (json.JSONDecodeError, TypeError):
                s03_for_shades = {}

            if s03_for_shades.get("status") == "ok":
                shade_table = pricing_loader.get_shade_pricing_table()
                shade_install = pricing_loader.get_shade_install_price()
                wall_table = pricing_loader.get_privacy_wall_pricing()
                wall_surcharges = pricing_loader.get_privacy_wall_surcharges()

                shades_ctx = {
                    "product_id": product_id,
                    "shades": {
                        "pricing_table": shade_table,
                        "install_price_per_shade": shade_install,
                        "rules": {
                            "round_up_to_whole_ft": True,
                        },
                    },
                    "privacy_walls": {
                        "pricing_table": wall_table,
                        "surcharges": wall_surcharges,
                        "rules": {
                            "center_support_threshold_width_ft": 10,
                            "round_up_to_whole_ft": True,
                            "solid_surcharge_pct": 25,
                        },
                    },
                    "input_from_s03": {
                        "comparison_mode": s03_for_shades.get("comparison_mode", False),
                        "result_single": s03_for_shades.get("result_single"),
                        "result_keep": s03_for_shades.get("result_keep"),
                        "result_swap": s03_for_shades.get("result_swap"),
                    },
                }
                pc["shades_privacy_context"] = json.dumps(shades_ctx)

        # ── trim_context — needed by Gate 9 ──
        trim_items = pricing_loader.get_trim_items(product_id)
        if trim_items:
            trim_ctx = {
                "product_id": product_id,
                "menu_items": trim_items,
                "rules": {
                    "max_one_trim_package": True,
                    "external_led_requires_2step_cornice": True,
                },
                "input_from_s03": {
                    "comparison_mode": False,
                    "result_single": None,
                },
            }
            # Populate S03 data if available
            if gate_3_resp:
                try:
                    s03_for_trim = json.loads(gate_3_resp) if isinstance(gate_3_resp, str) else gate_3_resp
                    if s03_for_trim.get("status") == "ok":
                        trim_ctx["input_from_s03"] = {
                            "comparison_mode": s03_for_trim.get("comparison_mode", False),
                            "result_single": s03_for_trim.get("result_single"),
                            "result_keep": s03_for_trim.get("result_keep"),
                            "result_swap": s03_for_trim.get("result_swap"),
                        }
                except (json.JSONDecodeError, TypeError):
                    pass
            pc["trim_context"] = json.dumps(trim_ctx)

        # ── electrical_scope_context — needed by Gate 10 ──
        # Combines heater/shade data from Gates 7 & 8 + electrical menu
        if gate_3_resp:
            try:
                s03_for_elec = json.loads(gate_3_resp) if isinstance(gate_3_resp, str) else gate_3_resp
            except (json.JSONDecodeError, TypeError):
                s03_for_elec = {}

            if s03_for_elec.get("status") == "ok":
                # Extract heater data from Gate 7
                has_heaters = False
                heater_qty = 0
                gate_7_resp = pc.get("gate_7_response")
                if gate_7_resp:
                    try:
                        s07 = json.loads(gate_7_resp) if isinstance(gate_7_resp, str) else gate_7_resp
                        has_heaters = s07.get("has_heaters", False)
                        heater_qty = s07.get("heater_qty", 0) or 0
                    except (json.JSONDecodeError, TypeError):
                        pass

                # Extract shade data from Gate 8
                has_shades = False
                shade_qty = 0
                gate_8_resp = pc.get("gate_8_response")
                if gate_8_resp:
                    try:
                        s08 = json.loads(gate_8_resp) if isinstance(gate_8_resp, str) else gate_8_resp
                        has_shades = s08.get("has_shades", False)
                        shade_qty = s08.get("shade_qty", 0) or 0
                    except (json.JSONDecodeError, TypeError):
                        pass

                electrical_items = pricing_loader.get_electrical_items()

                electrical_ctx = {
                    "product_id": product_id,
                    "has_heaters": has_heaters,
                    "heater_qty": heater_qty,
                    "has_shades": has_shades,
                    "shade_qty": shade_qty,
                    "electrical_menu": electrical_items,
                    "input_from_s03": {
                        "comparison_mode": s03_for_elec.get("comparison_mode", False),
                        "result_single": s03_for_elec.get("result_single"),
                        "result_keep": s03_for_elec.get("result_keep"),
                        "result_swap": s03_for_elec.get("result_swap"),
                    },
                }
                pc["electrical_scope_context"] = json.dumps(electrical_ctx)

        # ── installation_context — needed by Gate 11 ──
        # Combines product_id + install state + supply-only flag
        install_state = pc.get("install_state") or pc.get("state")
        installation_ctx = {
            "product_id": product_id,
            "install_state": install_state,
            "allow_supply_only": pc.get("allow_supply_only", False),
        }
        pc["installation_context"] = json.dumps(installation_ctx)

        # ── services_context — needed by Gate 12 ──
        # Combines product_id + custom service flag
        services_ctx = {
            "product_id": product_id,
            "allow_custom_service": pc.get("allow_custom_service", False),
        }
        pc["services_context"] = json.dumps(services_ctx)

        # ── quote_summary_context — needed by Gate 13 ──
        # Aggregates all gate responses into a single summary_inputs payload
        summary_inputs = {}
        gate_keys = [
            ("gate_3_response", "s03_bay_logic"),
            ("gate_4_response", "s04_base_pricing"),
            ("gate_5_response", "s05_finish"),
            ("gate_6_response", "s06_lighting_fans"),
            ("gate_7_response", "s07_heaters"),
            ("gate_8_response", "s08_shades_privacy"),
            ("gate_9_response", "s09_trim"),
            ("gate_10_response", "s10_electrical"),
            ("gate_11_response", "s11_installation"),
            ("gate_12_response", "s12_services"),
            ("gate_22_response", "s04b_structural"),
        ]
        for raw_key, label in gate_keys:
            raw = pc.get(raw_key)
            if raw:
                try:
                    summary_inputs[label] = json.loads(raw) if isinstance(raw, str) else raw
                except (json.JSONDecodeError, TypeError):
                    pass

        quote_summary_ctx = {
            "product_id": product_id,
            "project_state": pc.get("install_state") or pc.get("state"),
            "customer_name": pc.get("customer_name"),
            "summary_inputs": summary_inputs,
        }
        pc["quote_summary_context"] = json.dumps(quote_summary_ctx)

        # ── audit_context — needed by Gate 14 ──
        # Reuses the same aggregated gate responses as summary_inputs
        audit_ctx = {
            "product_id": product_id,
            "audit_inputs": summary_inputs,
            "flags": {
                "orientation_review_required": pc.get("orientation_review_required", False),
                "comparison_mode": pc.get("comparison_mode", False),
                "rep_override_required": pc.get("rep_override_required", False),
                "install_scope": pc.get("install_scope"),
            },
        }
        pc["audit_context"] = json.dumps(audit_ctx)

        # ── final_payload_context — needed by Gate 15 ──
        # Full step outputs + dimension/orientation data for final assembly
        step_outputs = dict(summary_inputs)  # reuse same aggregated responses
        # Add Gate 13 (summary) and Gate 14 (audit) if available
        for raw_key, label in [
            ("gate_13_response", "s13_summary"),
            ("gate_14_response", "s14_audit"),
        ]:
            raw = pc.get(raw_key)
            if raw:
                try:
                    step_outputs[label] = json.loads(raw) if isinstance(raw, str) else raw
                except (json.JSONDecodeError, TypeError):
                    pass

        # Include Gate 2 dimension data for final_dimensions resolution
        gate_2_resp = pc.get("gate_2_response")
        s02_data = {}
        if gate_2_resp:
            try:
                s02_data = json.loads(gate_2_resp) if isinstance(gate_2_resp, str) else gate_2_resp
            except (json.JSONDecodeError, TypeError):
                pass
        step_outputs["s02_dimensions"] = s02_data

        final_payload_ctx = {
            "product_id": product_id,
            "project_state": pc.get("install_state") or pc.get("state"),
            "customer_name": pc.get("customer_name"),
            "opportunity_id": pc.get("opportunity_id"),
            "comparison_mode": pc.get("comparison_mode", False),
            "orientation_choice": pc.get("orientation_choice"),
            "step_outputs": step_outputs,
        }
        pc["final_payload_context"] = json.dumps(final_payload_ctx)

        # ── breakdown_context — needed by Gate 16 ──
        # Passes the final payload's line items for detailed breakdown rendering
        gate_15_resp = pc.get("gate_15_response")
        line_items = []
        if gate_15_resp:
            try:
                s15 = json.loads(gate_15_resp) if isinstance(gate_15_resp, str) else gate_15_resp
                pricing_outputs = s15.get("pricing_outputs", {})
                # Collect line items from all category groups if available
                gate_13_resp = pc.get("gate_13_response")
                if gate_13_resp:
                    s13 = json.loads(gate_13_resp) if isinstance(gate_13_resp, str) else gate_13_resp
                    for group in s13.get("category_groups", []):
                        section = group.get("category", "")
                        for item in group.get("items", []):
                            line_items.append({
                                "section": section,
                                "description": item.get("label", ""),
                                "sku": item.get("sku"),
                                "qty": item.get("qty", 0),
                                "unit_price": item.get("unit_price"),
                                "subtotal": item.get("total"),
                                "is_structural_core": False,
                                "notes": [],
                            })
            except (json.JSONDecodeError, TypeError):
                pass

        breakdown_ctx = {
            "product_id": product_id,
            "line_items": line_items,
        }
        pc["breakdown_context"] = json.dumps(breakdown_ctx)

        # ── revision_context — needed by Gate 17 ──
        # Provides allowed revision targets and routing map
        revision_ctx = {
            "product_id": product_id,
            "allowed_revision_targets": [
                {"target": "dimensions", "route_to_step": "S02", "label": "Dimensions & State"},
                {"target": "orientation", "route_to_step": "S02b", "label": "Orientation"},
                {"target": "bay_logic", "route_to_step": "S03", "label": "Bay Logic"},
                {"target": "base_pricing", "route_to_step": "S04", "label": "Base Pricing"},
                {"target": "structural", "route_to_step": "S04b", "label": "Structural Add-Ons"},
                {"target": "color", "route_to_step": "S05", "label": "Color / Finish"},
                {"target": "lighting_fans", "route_to_step": "S06", "label": "Lighting & Fans"},
                {"target": "heaters", "route_to_step": "S07", "label": "Heaters"},
                {"target": "shades_privacy", "route_to_step": "S08", "label": "Shades & Privacy Walls"},
                {"target": "trim", "route_to_step": "S09", "label": "Trim & Architectural"},
                {"target": "electrical", "route_to_step": "S10", "label": "Electrical Scope"},
                {"target": "installation", "route_to_step": "S11", "label": "Installation Scope"},
                {"target": "services", "route_to_step": "S12", "label": "Design / Engineering / Permits"},
            ],
        }
        pc["revision_context"] = json.dumps(revision_ctx)

        # ── handoff_context — needed by Gate 18 ──
        # Provides audit results for finalization eligibility check
        gate_14_resp = pc.get("gate_14_response")
        audit_data = {}
        if gate_14_resp:
            try:
                audit_data = json.loads(gate_14_resp) if isinstance(gate_14_resp, str) else gate_14_resp
            except (json.JSONDecodeError, TypeError):
                pass

        handoff_ctx = {
            "product_id": product_id,
            "audit": {
                "blockers": audit_data.get("blockers", []),
                "warnings": audit_data.get("warnings", []),
                "confirmations": audit_data.get("confirmations", []),
                "override_notes": audit_data.get("override_notes", []),
            },
            "final_status": pc.get("final_status"),
        }
        pc["handoff_context"] = json.dumps(handoff_ctx)

    def should_skip_gate(self, gate_number: int, session: SessionState) -> bool:
        """Check if a gate should be skipped based on session state flags."""
        pc = session.product_config

        # Gate 19 (2b - Orientation): skip if orientation review NOT required
        if gate_number == 19:
            return pc.get("orientation_review_required") is not True

        # Gate 20 (3b - Threshold): skip unless dimensions are just over
        # single-bay limits (within 1 ft tolerance) AND multi-bay would result
        if gate_number == 20:
            total_bays = pc.get("total_bays")
            if total_bays is None or total_bays <= 1:
                return True  # Single bay or no data — no advisory needed
            # Check if either dimension is only slightly over the limit
            dim_rules = json.loads(settings.dimension_context)
            product_id = pc.get("product_id", "r_blade")
            rules = dim_rules.get("DIMENSION_RULES", {}).get(product_id, {})
            max_w = rules.get("max_width_single_bay_ft", 16)
            max_l = rules.get("max_length_single_bay_ft", 23)
            w = pc.get("width_ft_confirmed") or pc.get("width_ft_assumed")
            l = pc.get("length_ft_confirmed") or pc.get("length_ft_assumed")
            if w is None or l is None:
                return True
            w_over = (w - max_w) if w > max_w else 0
            l_over = (l - max_l) if l > max_l else 0
            # Trigger advisory only if overage is within 1 ft tolerance
            return not (0 < w_over <= 1 or 0 < l_over <= 1)

        # Gate 21 (3c - Dimension Router): only needed after Gate 20 ran
        # and the user chose to adjust or compare
        if gate_number == 21:
            return pc.get("advisory_triggered") is not True

        # Gate 22 (4b - Structural Add-Ons): skip if structure_type not set
        if gate_number == 22:
            return pc.get("structure_type") is None

        return False

    async def advance_gate(
        self, conversation_id: str, session: SessionState,
        parsed: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        """Advance to the next active gate and persist. Returns new gate number or None.

        Automatically skips conditional gates (19, 20, 21, 22) when their
        trigger conditions are not met.
        """
        if parsed and isinstance(parsed, dict):
            self.collect_data(session, parsed)
        nxt = session.advance()

        # Skip conditional gates whose trigger flags are not set
        while nxt is not None and self.should_skip_gate(nxt, session):
            nxt = session.advance()

        await self.save_session(conversation_id, session)
        return nxt


orchestrator = GateOrchestrator()
