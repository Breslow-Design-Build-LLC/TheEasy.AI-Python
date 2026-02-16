"""Supabase data-access layer for A.S.C.E.N.D. V3 orchestration tables.

Provides cached access to:
  - llm_models   (model registry)
  - agents       (4 agent definitions)
  - gates        (22 gate configs)
  - prompts      (versioned prompt storage)
  - gate_agent_map (which agents run on each gate)
  - conversations / conversation_messages (V3 session state)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Optional

from supabase import create_client

from ..config import settings

# ── Supabase client (singleton, same pattern as pricing_loader.py) ───────────

@lru_cache(maxsize=1)
def _get_client():
    """Create and cache the Supabase client."""
    return create_client(settings.supabase_url, settings.supabase_key)


def _service_client():
    """Return the Supabase client for service-role operations.

    Uses the service_role key when available (writes to RLS-protected tables),
    otherwise falls back to the anon key.
    """
    key = getattr(settings, "supabase_service_key", None) or settings.supabase_key
    return create_client(settings.supabase_url, key)


# ── In-memory caches ─────────────────────────────────────────────────────────

_models_cache: dict[str, dict[str, Any]] = {}
_agents_cache: dict[str, dict[str, Any]] = {}
_gates_cache: dict[int, dict[str, Any]] = {}
_gate_sequence_cache: list[int] | None = None
_gate_agent_map_cache: dict[int, list[dict[str, Any]]] = {}


def clear_cache() -> None:
    """Flush all in-memory caches (useful after config changes)."""
    _models_cache.clear()
    _agents_cache.clear()
    _gates_cache.clear()
    _gate_agent_map_cache.clear()
    global _gate_sequence_cache
    _gate_sequence_cache = None


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP A: Configuration Reads (cached, read-only)
# ═══════════════════════════════════════════════════════════════════════════════


# ── llm_models ────────────────────────────────────────────────────────────────

def get_llm_model(model_id: str) -> dict[str, Any] | None:
    """Return a single model row by model_id, with cache."""
    if model_id in _models_cache:
        return _models_cache[model_id]

    client = _get_client()
    resp = (
        client.table("llm_models")
        .select("*")
        .eq("model_id", model_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if resp.data:
        _models_cache[model_id] = resp.data[0]
        return resp.data[0]
    return None


def list_llm_models() -> list[dict[str, Any]]:
    """Return all active models."""
    client = _get_client()
    resp = (
        client.table("llm_models")
        .select("*")
        .eq("is_active", True)
        .order("provider")
        .execute()
    )
    rows = resp.data or []
    for r in rows:
        _models_cache[r["model_id"]] = r
    return rows


# ── agents ────────────────────────────────────────────────────────────────────

def get_agent(agent_slug: str) -> dict[str, Any] | None:
    """Return agent config by slug, with cache."""
    if agent_slug in _agents_cache:
        return _agents_cache[agent_slug]

    client = _get_client()
    resp = (
        client.table("agents")
        .select("*")
        .eq("slug", agent_slug)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if resp.data:
        _agents_cache[agent_slug] = resp.data[0]
        return resp.data[0]
    return None


def list_agents() -> list[dict[str, Any]]:
    """Return all active agents."""
    client = _get_client()
    resp = (
        client.table("agents")
        .select("*")
        .eq("is_active", True)
        .execute()
    )
    rows = resp.data or []
    for r in rows:
        _agents_cache[r["slug"]] = r
    return rows


# ── gates ─────────────────────────────────────────────────────────────────────

def get_gate(gate_number: int) -> dict[str, Any] | None:
    """Return gate config by gate_number, with cache."""
    if gate_number in _gates_cache:
        return _gates_cache[gate_number]

    client = _get_client()
    resp = (
        client.table("gates")
        .select("*")
        .eq("gate_number", gate_number)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if resp.data:
        _gates_cache[gate_number] = resp.data[0]
        return resp.data[0]
    return None


def list_gates() -> list[dict[str, Any]]:
    """Return all active gates ordered by sequence."""
    client = _get_client()
    resp = (
        client.table("gates")
        .select("*")
        .eq("is_active", True)
        .order("sequence_order")
        .execute()
    )
    rows = resp.data or []
    for r in rows:
        _gates_cache[r["gate_number"]] = r
    return rows


def get_gate_sequence() -> list[int]:
    """Return the ordered list of gate numbers (e.g. [1, 2, 19, 3, ...])."""
    global _gate_sequence_cache
    if _gate_sequence_cache is not None:
        return _gate_sequence_cache

    gates = list_gates()
    _gate_sequence_cache = [g["gate_number"] for g in gates]
    return _gate_sequence_cache


# ── prompts ───────────────────────────────────────────────────────────────────

def get_active_prompt(
    gate_number: int | None = None,
    prompt_type: str = "gate",
    agent_slug: str | None = None,
) -> dict[str, Any] | None:
    """Return the active prompt for a gate or agent.

    Uses the Supabase RPC function get_active_prompt for efficient lookup.
    """
    client = _get_client()
    try:
        resp = client.rpc(
            "get_active_prompt",
            {
                "p_gate_number": gate_number,
                "p_prompt_type": prompt_type,
                "p_agent_slug": agent_slug,
            },
        ).execute()
        if resp.data:
            return resp.data[0]
    except Exception:
        # Fallback to direct query if RPC fails
        query = (
            client.table("prompts")
            .select("*")
            .eq("prompt_type", prompt_type)
            .eq("is_active", True)
        )
        if gate_number is not None:
            query = query.eq("gate_number", gate_number)
        else:
            query = query.is_("gate_number", "null")
        if agent_slug is not None:
            query = query.eq("agent_slug", agent_slug)
        else:
            query = query.is_("agent_slug", "null")
        resp = query.limit(1).execute()
        if resp.data:
            return resp.data[0]
    return None


def get_master_prompt() -> str | None:
    """Return the active master system prompt text."""
    row = get_active_prompt(gate_number=None, prompt_type="master")
    if row:
        return row.get("developer_message")
    return None


# ── gate_agent_map ────────────────────────────────────────────────────────────

def get_agents_for_gate(gate_number: int) -> list[dict[str, Any]]:
    """Return agent mappings for a gate, ordered by execution_order."""
    if gate_number in _gate_agent_map_cache:
        return _gate_agent_map_cache[gate_number]

    client = _get_client()
    resp = (
        client.table("gate_agent_map")
        .select("*")
        .eq("gate_number", gate_number)
        .order("execution_order")
        .execute()
    )
    rows = resp.data or []
    _gate_agent_map_cache[gate_number] = rows
    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP B: Runtime / Session (Supabase conversations)
# ═══════════════════════════════════════════════════════════════════════════════


def create_conversation(
    customer_name: str | None = None,
    customer_email: str | None = None,
    opportunity_id: str | None = None,
    project_id: int | None = None,
) -> dict[str, Any]:
    """Create a new V3 conversation in Supabase. Returns the full row."""
    client = _service_client()
    row = {
        "customer_name": customer_name,
        "customer_email": customer_email,
        "opportunity_id": opportunity_id,
        "project_id": project_id,
        "current_gate": 1,
        "status": "active",
        "product_config": {},
        "comparison_mode": False,
        "total_gates_completed": 0,
        "total_api_calls": 0,
        "total_tokens_used": 0,
    }
    resp = client.table("conversations").insert(row).execute()
    return resp.data[0] if resp.data else row


def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    """Fetch a conversation by UUID."""
    client = _service_client()
    resp = (
        client.table("conversations")
        .select("*")
        .eq("id", conversation_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def update_conversation(conversation_id: str, updates: dict[str, Any]) -> None:
    """Patch a conversation row (current_gate, product_config, status, etc.)."""
    client = _service_client()
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    client.table("conversations").update(updates).eq("id", conversation_id).execute()


def get_session_state(conversation_id: str) -> dict[str, Any]:
    """Return the product_config + current_gate for a conversation."""
    conv = get_conversation(conversation_id)
    if not conv:
        return {}
    return {
        "current_gate": conv.get("current_gate", 1),
        "product_config": conv.get("product_config", {}),
        "comparison_mode": conv.get("comparison_mode", False),
        "status": conv.get("status", "active"),
        "total_gates_completed": conv.get("total_gates_completed", 0),
        "total_api_calls": conv.get("total_api_calls", 0),
        "total_tokens_used": conv.get("total_tokens_used", 0),
    }


def save_session_state(
    conversation_id: str,
    current_gate: int,
    product_config: dict[str, Any],
    comparison_mode: bool = False,
    total_gates_completed: int | None = None,
    total_api_calls: int | None = None,
    total_tokens_used: int | None = None,
) -> None:
    """Persist session state back to the conversations table."""
    updates: dict[str, Any] = {
        "current_gate": current_gate,
        "product_config": product_config,
        "comparison_mode": comparison_mode,
    }
    if total_gates_completed is not None:
        updates["total_gates_completed"] = total_gates_completed
    if total_api_calls is not None:
        updates["total_api_calls"] = total_api_calls
    if total_tokens_used is not None:
        updates["total_tokens_used"] = total_tokens_used
    update_conversation(conversation_id, updates)


# ── conversation_messages ─────────────────────────────────────────────────────

def add_message(
    conversation_id: str,
    role: str,
    content: str,
    gate_number: int | None = None,
    response_json: dict[str, Any] | None = None,
    metadata_json: dict[str, Any] | None = None,
    agent_slug: str | None = None,
    model_used: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    latency_ms: int | None = None,
) -> dict[str, Any]:
    """Insert a message into conversation_messages."""
    client = _service_client()
    row = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "gate_number": gate_number,
        "response_json": response_json,
        "metadata_json": metadata_json,
        "agent_slug": agent_slug,
        "model_used": model_used,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
    }
    resp = client.table("conversation_messages").insert(row).execute()
    return resp.data[0] if resp.data else row


def get_messages(
    conversation_id: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return messages for a conversation, oldest first."""
    client = _service_client()
    resp = (
        client.table("conversation_messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .limit(limit)
        .execute()
    )
    return resp.data or []


def get_conversation_history(conversation_id: str) -> list[dict[str, str]]:
    """Return messages in OpenAI chat format [{role, content}, ...]."""
    messages = get_messages(conversation_id)
    return [{"role": m["role"], "content": m["content"]} for m in messages]


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP C: Audit Writes (append-only)
# ═══════════════════════════════════════════════════════════════════════════════


def log_gate_result(
    conversation_id: str,
    gate_number: int,
    status: str,
    result_json: dict[str, Any],
    pricing_data: dict[str, Any] | None = None,
    context_snapshot: dict[str, Any] | None = None,
    was_auto_advanced: bool = False,
    was_chain_advanced: bool = False,
    model_used: str | None = None,
    attempt_count: int = 1,
) -> None:
    """Insert or upsert a gate_result row."""
    client = _service_client()
    row = {
        "conversation_id": conversation_id,
        "gate_number": gate_number,
        "status": status,
        "result_json": result_json,
        "pricing_data": pricing_data,
        "context_snapshot": context_snapshot,
        "was_auto_advanced": was_auto_advanced,
        "was_chain_advanced": was_chain_advanced,
        "model_used": model_used,
        "attempt_count": attempt_count,
    }
    # Upsert on (conversation_id, gate_number) to handle re-runs during revision
    client.table("gate_results").upsert(
        row, on_conflict="conversation_id,gate_number"
    ).execute()


def log_agent_decision(
    conversation_id: str,
    gate_number: int,
    agent_slug: str,
    action: str,
    reasoning: str,
    target_gate: int | None = None,
    confidence: float | None = None,
    input_summary: str | None = None,
    session_snapshot: dict[str, Any] | None = None,
) -> None:
    """Append an agent_decisions row (immutable audit trail)."""
    client = _service_client()
    client.table("agent_decisions").insert({
        "conversation_id": conversation_id,
        "gate_number": gate_number,
        "agent_slug": agent_slug,
        "action": action,
        "reasoning": reasoning,
        "target_gate": target_gate,
        "confidence": confidence,
        "input_summary": input_summary,
        "session_snapshot": session_snapshot,
    }).execute()


def log_compliance_check(
    conversation_id: str,
    gate_number: int,
    passed: bool,
    checks_run: list[str],
    violations: list[str] | None = None,
    warnings: list[str] | None = None,
    hallucination_score: float | None = None,
    gate_output_snapshot: dict[str, Any] | None = None,
    pricing_context_snapshot: dict[str, Any] | None = None,
    model_used: str | None = None,
    latency_ms: int | None = None,
) -> None:
    """Append a compliance_checks row."""
    client = _service_client()
    client.table("compliance_checks").insert({
        "conversation_id": conversation_id,
        "gate_number": gate_number,
        "passed": passed,
        "checks_run": checks_run,
        "violations": violations or [],
        "warnings": warnings or [],
        "hallucination_score": hallucination_score,
        "gate_output_snapshot": gate_output_snapshot,
        "pricing_context_snapshot": pricing_context_snapshot,
        "model_used": model_used,
        "latency_ms": latency_ms,
    }).execute()


def log_pricing_trace(
    conversation_id: str,
    gate_number: int,
    operation: str,
    input_data: dict[str, Any],
    output_data: dict[str, Any],
    math_trace: str,
    source_product_id: int | None = None,
    source_variant_id: int | None = None,
) -> None:
    """Append a pricing_traces row."""
    client = _service_client()
    client.table("pricing_traces").insert({
        "conversation_id": conversation_id,
        "gate_number": gate_number,
        "operation": operation,
        "input_data": input_data,
        "output_data": output_data,
        "math_trace": math_trace,
        "source_product_id": source_product_id,
        "source_variant_id": source_variant_id,
    }).execute()
