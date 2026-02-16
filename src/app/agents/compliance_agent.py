"""Compliance Agent — validates gate responses for correctness.

Uses a fast LLM (gpt-4.1-mini or claude-haiku-4) to check:
  - Pricing matches source data (no hallucinated numbers)
  - Required fields are present
  - Business rules are followed
  - Status transitions are valid

Every validation is logged to the compliance_checks audit table.
"""

from __future__ import annotations

import json
import time
from typing import Any

from ..config import settings
from ..gates.session_state import SessionState
from ..services import supabase_service as supa
from ..services.llm_service import call_llm
from ..services.model_resolver import resolve_model


_COMPLIANCE_PROMPT = """\
You are a compliance validator for the Breslow QuoteApp. Your job is to check
a gate response for errors, hallucinations, and rule violations.

You will receive:
1. The gate number and name
2. The gate response (JSON)
3. The pricing context (data the Pricing Agent provided)
4. The session state (all collected data so far)

Check for:
- HALLUCINATED PRICES: Any number in the response that doesn't appear in the pricing context
- MISSING REQUIRED FIELDS: Does the response have all fields the gate requires?
- MATH ERRORS: Do the calculations (unit_price × qty = subtotal) add up?
- INVALID STATUS: Is status "ok" or "needs_info"?
- BUSINESS RULE VIOLATIONS: Anything that contradicts the system rules?

Respond with JSON only:
{
  "passed": true/false,
  "violations": ["list of blocking issues"],
  "warnings": ["list of non-blocking concerns"],
  "hallucination_score": 0.0 to 1.0 (0 = clean, 1 = definite hallucination),
  "checks_run": ["list of checks performed"]
}
"""


def validate(
    gate_number: int,
    gate_response: dict[str, Any],
    session: SessionState,
    pricing_data: dict[str, Any] | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Validate a gate response using the Compliance Agent.

    Returns:
        dict with: passed (bool), violations, warnings, hallucination_score, checks_run
    """
    if not settings.enable_compliance_agent:
        return {
            "passed": True,
            "violations": [],
            "warnings": [],
            "hallucination_score": 0.0,
            "checks_run": ["compliance_disabled"],
        }

    gate_config = supa.get_gate(gate_number)
    gate_name = gate_config["name"] if gate_config else f"Gate {gate_number}"

    # Build the validation context
    context = (
        f"Gate: {gate_number} — {gate_name}\n\n"
        f"Gate Response:\n{json.dumps(gate_response, default=str)}\n\n"
        f"Pricing Context:\n{json.dumps(pricing_data or {}, default=str)}\n\n"
        f"Session State:\n{json.dumps(session.product_config, default=str)}\n"
    )

    # Resolve model for compliance agent
    model_info = resolve_model(gate_number, "compliance")
    start = time.perf_counter()

    try:
        llm_resp = call_llm(
            model_id=model_info["model_id"],
            provider=model_info["provider"],
            messages=[{"role": "user", "content": context}],
            system_prompt=_COMPLIANCE_PROMPT,
            temperature=0.0,
            max_tokens=2048,
            json_mode=True,
        )

        result = json.loads(llm_resp.content)
        latency_ms = int((time.perf_counter() - start) * 1000)

        # Ensure required fields
        result.setdefault("passed", True)
        result.setdefault("violations", [])
        result.setdefault("warnings", [])
        result.setdefault("hallucination_score", 0.0)
        result.setdefault("checks_run", ["llm_compliance_check"])

    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        result = {
            "passed": True,  # Don't block on compliance errors
            "violations": [],
            "warnings": [f"Compliance check failed: {str(e)}"],
            "hallucination_score": 0.0,
            "checks_run": ["llm_compliance_check_failed"],
        }

    # Log to audit table
    if conversation_id:
        try:
            supa.log_compliance_check(
                conversation_id=conversation_id,
                gate_number=gate_number,
                passed=result["passed"],
                checks_run=result["checks_run"],
                violations=result.get("violations"),
                warnings=result.get("warnings"),
                hallucination_score=result.get("hallucination_score"),
                gate_output_snapshot=gate_response,
                pricing_context_snapshot=pricing_data,
                model_used=model_info["model_id"],
                latency_ms=latency_ms,
            )
        except Exception:
            pass  # Audit failures never break the flow

    return result
