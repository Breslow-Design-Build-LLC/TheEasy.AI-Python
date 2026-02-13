"""Per-conversation session state, serialized to the config_json column."""

from __future__ import annotations

import dataclasses
from typing import Any, Optional

from .models import GateStatus
from .registry import GATE_REGISTRY


@dataclasses.dataclass
class SessionState:
    current_gate: int = 1
    gate_sequence: list[int] = dataclasses.field(
        default_factory=lambda: [1, 2, 17, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    )
    product_config: dict[str, Any] = dataclasses.field(default_factory=dict)
    line_items: list[dict] = dataclasses.field(default_factory=list)
    subtotals_by_gate: dict[str, float] = dataclasses.field(default_factory=dict)
    flags: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionState:
        if not data:
            return cls()
        return cls(
            current_gate=data.get("current_gate", 1),
            gate_sequence=data.get("gate_sequence", [1, 2, 17, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]),
            product_config=data.get("product_config", {}),
            line_items=data.get("line_items", []),
            subtotals_by_gate=data.get("subtotals_by_gate", {}),
            flags=data.get("flags", []),
        )

    def next_gate(self) -> Optional[int]:
        """Return the next active gate number after current_gate, skipping placeholders."""
        seq = self.gate_sequence
        try:
            idx = seq.index(self.current_gate)
        except ValueError:
            return None
        for candidate in seq[idx + 1 :]:
            gate_cfg = GATE_REGISTRY.get(candidate)
            if gate_cfg and gate_cfg.status == GateStatus.ACTIVE:
                return candidate
        return None

    def advance(self) -> Optional[int]:
        """Move current_gate to the next active gate. Returns new gate number or None."""
        nxt = self.next_gate()
        if nxt is not None:
            self.current_gate = nxt
        return nxt
