"""Pydantic request / response models for the QuoteApp API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Shared / Reusable ──────────────────────────────────────────────

class ErrorDetail(BaseModel):
    code: str = "error"
    message: str


class ErrorResponse(BaseModel):
    """Top-level error envelope expected by ExternalAPIService.ts."""
    error: ErrorDetail


# ── Health ──────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"


# ── Conversations ───────────────────────────────────────────────────

class CreateConversationRequest(BaseModel):
    client_id: int
    user_id: int
    config: Optional[dict[str, Any]] = None


class CreateConversationResponse(BaseModel):
    conversation_id: str
    status: str
    created_at: str


class CancelConversationResponse(BaseModel):
    conversation_id: str
    status: str


# ── Messages ────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    message: str
    client_id: int
    user_id: int


class MessageItem(BaseModel):
    """Single message in a conversation."""
    id: str
    conversation_id: str
    role: str
    content: str
    response: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: str


class MessageListResponse(BaseModel):
    messages: list[MessageItem]


class ExternalAPIResponse(BaseModel):
    """Full JSON response from sendMessage (non-streaming)."""
    conversation_id: str
    message_id: str
    role: str = "assistant"
    content: str
    response: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None
    created_at: str


# ── SSE Event Data ──────────────────────────────────────────────────

class StreamChunkData(BaseModel):
    """Data payload inside an SSE `chunk` event."""
    conversation_id: str
    delta: str


class StreamDoneData(BaseModel):
    """Data payload inside an SSE `done` event."""
    conversation_id: str
    message_id: str
    content: str
    response: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None
