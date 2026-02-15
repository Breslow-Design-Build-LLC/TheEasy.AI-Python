"""Build a unified `display` object for every API response."""

from __future__ import annotations

import re
from typing import Any, Optional

# Regex: "A) Label" or "A. Label" or "A- Label" anywhere in text
# Lookahead detects next option separated by comma, newline, or space
_OPTION_RE = re.compile(
    r"(?:^|[\s,;])\s*([A-Z])\s*[).\-]\s*(.+?)(?=\s+[A-Z]\s*[).\-]\s|[,;]\s*[A-Z]\s*[).\-]|\n\s*[A-Z]\s*[).\-]|$)",
    re.DOTALL,
)


def parse_options(text: str) -> list[dict[str, str]]:
    """Extract structured options from question text like 'A) R-Blade\\nB) R-Breeze'.

    Validates that letters start from A and are consecutive to avoid false positives.
    Returns list of {"key": "A", "label": "R-Blade", "value": "r_blade"}.
    """
    matches = _OPTION_RE.findall(text)
    if not matches:
        return []

    # Validate consecutive letters starting from A
    for i, (letter, _) in enumerate(matches):
        expected = chr(ord("A") + i)
        if letter != expected:
            return []

    options = []
    for letter, label in matches:
        label = label.strip().rstrip(",")
        value = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
        options.append({"key": letter, "label": label, "value": value})
    return options


def _extract_message(response_dict: Optional[dict[str, Any]]) -> Optional[str]:
    """Unify 'question' (string, Gate 1) vs 'questions' (array, Gates 2+)."""
    if not response_dict or not isinstance(response_dict, dict):
        return None

    # Gate 1 style: "question" is a string
    q = response_dict.get("question")
    if isinstance(q, str) and q.strip():
        return q.strip()

    # Gates 2+ style: "questions" is an array of strings
    qs = response_dict.get("questions")
    if isinstance(qs, list) and qs:
        return "\n".join(str(item) for item in qs if item)

    return None


def build_display(
    parsed: Optional[dict[str, Any]],
    raw_text: str,
    metadata: dict[str, Any],
    gate_number: int,
    gate_name: str,
) -> dict[str, Any]:
    """Build the unified display object for a gate response.

    Handles normal questions, gate advancement (with next_gate), and errors.
    """
    advanced_to = metadata.get("advanced_to_gate")
    next_gate = metadata.get("next_gate")
    next_gate_error = metadata.get("next_gate_error")

    # -- Determine effective gate info and message --
    if advanced_to and next_gate:
        # Gate advanced and auto-fetch succeeded
        eff_gate_number = next_gate["gate_number"]
        eff_gate_name = next_gate["gate_name"]
        next_resp = next_gate.get("response")
        if isinstance(next_resp, dict):
            message = _extract_message(next_resp) or raw_text
        elif isinstance(next_resp, str):
            message = next_resp
        else:
            message = raw_text
        # Parse options from the next gate's message
        options = parse_options(message)
        status = _resolve_status(next_resp if isinstance(next_resp, dict) else None)
    elif advanced_to and next_gate_error:
        # Gate advanced but auto-fetch failed
        eff_gate_number = advanced_to
        eff_gate_name = f"Gate {advanced_to}"
        message = "Moving to next step..."
        options = []
        status = "error"
    else:
        # Normal (no advancement)
        eff_gate_number = gate_number
        eff_gate_name = gate_name
        message = _extract_message(parsed) if parsed else None
        if not message:
            message = raw_text
        options = parse_options(message)
        status = _resolve_status(parsed)

    # -- Warnings --
    warnings: list[str] = []
    if parsed and isinstance(parsed, dict):
        w = parsed.get("warnings")
        if isinstance(w, list):
            warnings = [str(item) for item in w if item]
    # Also check next_gate response for warnings
    if next_gate and isinstance(next_gate.get("response"), dict):
        w = next_gate["response"].get("warnings")
        if isinstance(w, list):
            warnings = [str(item) for item in w if item]

    return {
        "message": message,
        "options": options,
        "warnings": warnings,
        "error": None,
        "gate_number": eff_gate_number,
        "gate_name": eff_gate_name,
        "status": status,
    }


def build_error_display(
    code: str = "error",
    message: str = "An error occurred",
    gate_number: int = 0,
    gate_name: str = "",
) -> dict[str, Any]:
    """Build a display object for error scenarios."""
    return {
        "message": message,
        "options": [],
        "warnings": [],
        "error": {"code": code, "message": message},
        "gate_number": gate_number,
        "gate_name": gate_name,
        "status": "error",
    }


def _resolve_status(parsed: Optional[dict[str, Any]]) -> str:
    """Map the parsed response status to a display status."""
    if not parsed or not isinstance(parsed, dict):
        return "needs_info"
    raw = str(parsed.get("status", "")).lower()
    if raw in ("ok", "complete", "done"):
        return raw
    return "needs_info"
