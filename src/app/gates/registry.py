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
        status=GateStatus.ACTIVE,
    ),
    3: GateConfig(
        number=3,
        name="Bay Logic & Pricing",
        gate_type=GateType.UNIVERSAL,
    ),
    4: GateConfig(
        number=4,
        name="Structure & Posts",
        gate_type=GateType.UNIVERSAL,
    ),
    5: GateConfig(
        number=5,
        name="Color / Finish",
        gate_type=GateType.CONFIG_RESTRICTED,
    ),
    6: GateConfig(
        number=6,
        name="Roof Options",
        gate_type=GateType.UNIVERSAL,
    ),
    7: GateConfig(
        number=7,
        name="Electrical & Lighting",
        gate_type=GateType.UNIVERSAL,
    ),
    8: GateConfig(
        number=8,
        name="Fan & Heating",
        gate_type=GateType.UNIVERSAL,
    ),
    9: GateConfig(
        number=9,
        name="Screens & Enclosures",
        gate_type=GateType.UNIVERSAL,
    ),
    10: GateConfig(
        number=10,
        name="Permits & Engineering",
        gate_type=GateType.UNIVERSAL,
    ),
    11: GateConfig(
        number=11,
        name="Installation Options",
        gate_type=GateType.UNIVERSAL,
    ),
    12: GateConfig(
        number=12,
        name="Warranty & Protection",
        gate_type=GateType.UNIVERSAL,
    ),
    13: GateConfig(
        number=13,
        name="Discounts & Promotions",
        gate_type=GateType.UNIVERSAL,
    ),
    14: GateConfig(
        number=14,
        name="Summary & Review",
        gate_type=GateType.UNIVERSAL,
    ),
    15: GateConfig(
        number=15,
        name="Customer Info & Delivery",
        gate_type=GateType.UNIVERSAL,
    ),
    16: GateConfig(
        number=16,
        name="Final Quote & Checkout",
        gate_type=GateType.UNIVERSAL,
    ),
}

DEFAULT_GATE_SEQUENCE: list[int] = list(range(1, 17))


def get_gate(number: int) -> GateConfig:
    """Return a gate config by number, or raise KeyError."""
    return GATE_REGISTRY[number]


def get_active_gates() -> list[GateConfig]:
    """Return only gates that have ACTIVE status (real prompt IDs)."""
    return [g for g in GATE_REGISTRY.values() if g.status == GateStatus.ACTIVE]
