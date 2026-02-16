"""V3 API router — A.S.C.E.N.D. multi-agent endpoints.

Same response format as V1/V2 for backward compatibility with the UI app.
Uses Supabase for conversations (instead of SQLite) and the multi-agent
orchestrator for processing.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from ..auth import verify_token
from ..models.schemas import SendMessageRequest
from ..services import supabase_service as supa
from ..services.orchestrator_v3 import OrchestratorV3

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v3", tags=["V3 — A.S.C.E.N.D."])

_orchestrator = OrchestratorV3()


# ── Conversations ─────────────────────────────────────────────────────────────

@router.post("/conversations", dependencies=[Depends(verify_token)])
async def create_conversation(
    body: dict[str, Any] | None = None,
):
    """Create a new V3 conversation (stored in Supabase)."""
    body = body or {}
    conv = supa.create_conversation(
        customer_name=body.get("customer_name"),
        customer_email=body.get("customer_email"),
        opportunity_id=body.get("opportunity_id"),
        project_id=body.get("project_id"),
    )
    return {
        "conversation_id": conv["id"],
        "status": conv.get("status", "active"),
        "created_at": conv.get("started_at"),
    }


@router.delete("/conversations/{conversation_id}", dependencies=[Depends(verify_token)])
async def cancel_conversation(conversation_id: str):
    """Cancel a V3 conversation."""
    conv = supa.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    supa.update_conversation(conversation_id, {"status": "cancelled"})
    return {"conversation_id": conversation_id, "status": "cancelled"}


# ── Messages ──────────────────────────────────────────────────────────────────

@router.post(
    "/conversations/{conversation_id}/messages",
    dependencies=[Depends(verify_token)],
)
async def send_message(conversation_id: str, body: SendMessageRequest):
    """Send a user message and get the V3 multi-agent response."""
    # Verify conversation exists
    conv = supa.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conv.get("status") != "active":
        raise HTTPException(status_code=400, detail=f"Conversation is {conv['status']}")

    try:
        result = _orchestrator.handle_message(conversation_id, body.message)
    except Exception as e:
        logger.exception(f"V3 orchestrator error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Return in ExternalAPIResponse format (same as V1/V2)
    return {
        "conversation_id": conversation_id,
        "gate_number": result.get("gate_number"),
        "gate_name": result.get("gate_name"),
        "response": result.get("response"),
        "display": result.get("display"),
        "metadata": result.get("metadata"),
    }


@router.post(
    "/conversations/{conversation_id}/messages/stream",
    dependencies=[Depends(verify_token)],
)
async def send_message_stream(conversation_id: str, body: SendMessageRequest):
    """Stream a V3 response via SSE."""
    conv = supa.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conv.get("status") != "active":
        raise HTTPException(status_code=400, detail=f"Conversation is {conv['status']}")

    def event_generator():
        try:
            for event in _orchestrator.handle_message_stream(conversation_id, body.message):
                event_type = event.get("event", "chunk")
                data = json.dumps(event.get("data", {}), default=str)
                yield {"event": event_type, "data": data}
        except Exception as e:
            logger.exception(f"V3 stream error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())


@router.get(
    "/conversations/{conversation_id}/messages",
    dependencies=[Depends(verify_token)],
)
async def get_messages(
    conversation_id: str,
    limit: int = Query(default=50, le=200),
):
    """List messages for a V3 conversation."""
    conv = supa.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = supa.get_messages(conversation_id, limit=limit)

    return {
        "conversation_id": conversation_id,
        "status": conv.get("status", "active"),
        "messages": [
            {
                "id": m.get("id"),
                "role": m.get("role"),
                "content": m.get("content"),
                "gate_number": m.get("gate_number"),
                "response": m.get("response_json"),
                "metadata": m.get("metadata_json"),
                "created_at": m.get("created_at"),
            }
            for m in messages
        ],
    }


# ── Health Check ──────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    """V3 health check — verify Supabase connectivity."""
    try:
        gates = supa.list_gates()
        models = supa.list_llm_models()
        agents = supa.list_agents()
        return {
            "status": "ok",
            "version": "3.0.0",
            "engine": "A.S.C.E.N.D.",
            "gates_loaded": len(gates),
            "models_loaded": len(models),
            "agents_loaded": len(agents),
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": str(e)},
        )
