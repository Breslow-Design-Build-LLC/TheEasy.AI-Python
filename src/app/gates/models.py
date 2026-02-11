"""Gate configuration data models."""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Optional


class GateType(str, Enum):
    UNIVERSAL = "universal"          # works for all products
    CONFIG_RESTRICTED = "config"     # varies by product


class GateStatus(str, Enum):
    ACTIVE = "active"                # has prompt_id, ready to use
    PLACEHOLDER = "placeholder"      # defined but no prompt yet


@dataclasses.dataclass(frozen=True)
class GateConfig:
    number: int                                  # 1-16
    name: str                                    # human-readable
    gate_type: GateType
    prompt_id: Optional[str] = None
    prompt_version: Optional[str] = None
    variables_template: dict[str, str] = dataclasses.field(default_factory=dict)
    tools_required: list[str] = dataclasses.field(default_factory=list)
    status: GateStatus = GateStatus.PLACEHOLDER
