"""Single source of truth for all 16 gate definitions."""

from __future__ import annotations

from ..config import settings
from .models import GateConfig, GateStatus, GateType

GATE_REGISTRY: dict[int, GateConfig] = {
    1: GateConfig(
        number=1,
        name="Product Selection",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate1,
        prompt_version=settings.openai_prompt_version,
        variables_template={"product_options": "product_options"},
        status=GateStatus.ACTIVE,
    ),
    2: GateConfig(
        number=2,
        name="Dimensions & State",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate2,
        variables_template={
            "dimension_context": "dimension_context",
        },
        status=GateStatus.ACTIVE,
    ),
    3: GateConfig(
        number=3,
        name="Bay Logic & Pricing",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate3,
        variables_template={
            "bay_logic_context": "bay_logic_context",
        },
        status=GateStatus.ACTIVE,
    ),
    4: GateConfig(
        number=4,
        name="Structure & Posts",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate4,
        prompt_version="2",
        variables_template={
            "product_options": "product_id",
            "total_bays": "total_bays",
        },
        status=GateStatus.ACTIVE,
    ),
    5: GateConfig(
        number=5,
        name="Color / Finish",
        gate_type=GateType.CONFIG_RESTRICTED,
        prompt_id=settings.openai_prompt_id_gate5,
        prompt_version="2",
        variables_template={
            "product_id": "product_id",
            "structure_type": "structure_type",
        },
        status=GateStatus.ACTIVE,
    ),
    6: GateConfig(
        number=6,
        name="Roof Options",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate6,
        prompt_version="2",
        variables_template={
            "product_id": "product_id",
            "quote_context": "quote_context",
        },
        status=GateStatus.ACTIVE,
    ),
    7: GateConfig(
        number=7,
        name="Electrical & Lighting",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate7,
        prompt_version="2",
        variables_template={
            "product_id": "product_id",
            "quote_context": "quote_context",
        },
        status=GateStatus.ACTIVE,
    ),
    8: GateConfig(
        number=8,
        name="Fan & Heating",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate8,
        prompt_version="2",
        variables_template={
            "product_id": "product_id",
            "quote_context": "quote_context",
        },
        status=GateStatus.ACTIVE,
    ),
    9: GateConfig(
        number=9,
        name="Screens & Enclosures",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate9,
        prompt_version="2",
        variables_template={
            "product_id": "product_id",
            "quote_context": "quote_context",
        },
        status=GateStatus.ACTIVE,
    ),
    10: GateConfig(
        number=10,
        name="Permits & Engineering",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate10,
        prompt_version="2",
        variables_template={
            "product_id": "product_id",
            "quote_context": "quote_context",
        },
        status=GateStatus.ACTIVE,
    ),
    11: GateConfig(
        number=11,
        name="Installation Options",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate11,
        prompt_version="2",
        variables_template={
            "product_id": "product_id",
            "quote_context": "quote_context",
        },
        status=GateStatus.ACTIVE,
    ),
    12: GateConfig(
        number=12,
        name="Warranty & Protection",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate12,
        prompt_version="2",
        variables_template={
            "product_id": "product_id",
            "quote_context": "quote_context",
        },
        status=GateStatus.ACTIVE,
    ),
    13: GateConfig(
        number=13,
        name="Discounts & Promotions",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate13,
        prompt_version="2",
        variables_template={
            "product_id": "product_id",
            "total_bays": "total_bays",
            "quote_context": "quote_context",
        },
        status=GateStatus.ACTIVE,
    ),
    14: GateConfig(
        number=14,
        name="Summary & Review",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate14,
        prompt_version="2",
        variables_template={
            "product_id": "product_id",
            "quote_context": "quote_context",
        },
        status=GateStatus.ACTIVE,
    ),
    15: GateConfig(
        number=15,
        name="Customer Info & Delivery",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate15,
        prompt_version="2",
        variables_template={
            "product_id": "product_id",
            "state": "state",
        },
        status=GateStatus.ACTIVE,
    ),
    16: GateConfig(
        number=16,
        name="Final Quote & Checkout",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate16,
        prompt_version="2",
        variables_template={
            "product_id": "product_id",
            "resolved_pricing_items": "resolved_pricing_items",
            "package_definitions": "package_definitions",
            "missing_price_flags": "missing_price_flags",
        },
        status=GateStatus.ACTIVE,
    ),
    17: GateConfig(
        number=17,
        name="Revisions",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate17,
        variables_template={
            "product_id": "product_id",
            "quote_context": "quote_context",
        },
        status=GateStatus.ACTIVE,
    ),
    18: GateConfig(
        number=18,
        name="Post-Quote Handoff & Finalize",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate18,
        variables_template={
            "product_id": "product_id",
            "quote_context": "quote_context",
        },
        status=GateStatus.ACTIVE,
    ),
    19: GateConfig(
        number=19,
        name="Orientation Confirmation",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate2b,
        variables_template={
            "orientation_context": "gate_2_response",
        },
        status=GateStatus.ACTIVE,
    ),
    20: GateConfig(
        number=20,
        name="Threshold Advisory",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate3b,
        variables_template={
            "threshold_advisory_context": "gate_3_response",
        },
        status=GateStatus.ACTIVE,
    ),
    21: GateConfig(
        number=21,
        name="Dimension Router",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate3c,
        variables_template={
            "dimension_router_context": "gate_3_response",
        },
        status=GateStatus.ACTIVE,
    ),
    22: GateConfig(
        number=22,
        name="Structural Add-Ons Package Rules",
        gate_type=GateType.UNIVERSAL,
        prompt_id=settings.openai_prompt_id_gate4b,
        variables_template={
            "product_id": "product_id",
            "quote_context": "quote_context",
        },
        status=GateStatus.ACTIVE,
    ),
}

DEFAULT_GATE_SEQUENCE: list[int] = [1, 2, 19, 3, 20, 21, 4, 22, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]


def get_gate(number: int) -> GateConfig:
    """Return a gate config by number, or raise KeyError."""
    return GATE_REGISTRY[number]


def get_active_gates() -> list[GateConfig]:
    """Return only gates that have ACTIVE status (real prompt IDs)."""
    return [g for g in GATE_REGISTRY.values() if g.status == GateStatus.ACTIVE]
