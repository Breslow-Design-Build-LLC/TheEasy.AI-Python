"""Message send / list / stream endpoints."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sse_starlette.sse import EventSourceResponse

from ..auth import require_bearer_token
from ..models.schemas import (
    ExternalAPIResponse,
    MessageListResponse,
    MessageItem,
    SendMessageRequest,
    StreamChunkData,
    StreamDoneData,
)
from ..services import conversation_service as conv_svc
from ..services import quote_service

router = APIRouter(
    prefix="/api/v1/conversations/{conversation_id}/messages",
    tags=["messages"],
    dependencies=[Depends(require_bearer_token)],
)


async def _require_active_conversation(conversation_id: str) -> dict:
    conv = await conv_svc.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Conversation not found"}},
        )
    if conv["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "conversation_inactive", "message": "Conversation is not active"}},
        )
    return conv


@router.post("", response_model=ExternalAPIResponse, status_code=status.HTTP_200_OK)
async def send_message(conversation_id: str, body: SendMessageRequest):
    await _require_active_conversation(conversation_id)

    try:
        msg = await quote_service.handle_message(conversation_id, body.message)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"code": "openai_error", "message": str(exc)}},
        )

    meta = msg.get("metadata") or {}
    return ExternalAPIResponse(
        conversation_id=conversation_id,
        message_id=msg["id"],
        role=msg["role"],
        content=msg["content"],
        response=msg.get("response"),
        metadata=meta,
        created_at=msg["created_at"],
        gate_number=meta.get("gate_number"),
        gate_name=meta.get("gate_name"),
    )


@router.get("", response_model=MessageListResponse)
async def get_messages(
    conversation_id: str,
    after: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    conv = await conv_svc.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Conversation not found"}},
        )

    rows = await conv_svc.get_messages(conversation_id, after=after, limit=limit)
    items = [
        MessageItem(
            id=r["id"],
            conversation_id=r["conversation_id"],
            role=r["role"],
            content=r["content"],
            response=r.get("response"),
            metadata=r.get("metadata"),
            created_at=r["created_at"],
        )
        for r in rows
    ]
    return MessageListResponse(conversation_status=conv["status"], messages=items)


@router.post("/stream", status_code=status.HTTP_200_OK)
async def send_message_stream(conversation_id: str, body: SendMessageRequest):
    await _require_active_conversation(conversation_id)

    async def event_generator():
        try:
            async for event in quote_service.handle_message_stream(
                conversation_id, body.message
            ):
                if event["type"] == "chunk":
                    data = StreamChunkData(
                        conversation_id=conversation_id,
                        delta=event["delta"],
                    )
                    yield {"event": "chunk", "data": data.model_dump_json()}
                elif event["type"] == "done":
                    msg = event["message"]
                    meta = msg.get("metadata") or {}
                    data = StreamDoneData(
                        conversation_id=conversation_id,
                        message_id=msg["id"],
                        content=msg["content"],
                        response=msg.get("response"),
                        metadata=meta,
                        gate_number=meta.get("gate_number"),
                        gate_name=meta.get("gate_name"),
                    )
                    yield {"event": "done", "data": data.model_dump_json()}
        except Exception as exc:
            error_data = json.dumps({"error": {"code": "openai_error", "message": str(exc)}})
            yield {"event": "error", "data": error_data}

    return EventSourceResponse(event_generator())
