"""Conversation create / cancel endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import require_bearer_token
from ..models.schemas import (
    CreateConversationRequest,
    CreateConversationResponse,
    CancelConversationResponse,
    ErrorResponse,
)
from ..services import conversation_service as conv_svc

router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["conversations"],
    dependencies=[Depends(require_bearer_token)],
)


@router.post(
    "",
    response_model=CreateConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(body: CreateConversationRequest):
    result = await conv_svc.create_conversation(
        client_id=body.client_id,
        user_id=body.user_id,
        config=body.config,
    )
    return result



@router.delete(
    "/{conversation_id}",
    response_model=CancelConversationResponse,
)
async def cancel_conversation(
    conversation_id: str,
    hard_delete: bool = Query(False, description="Removes conversation and messages from Database"),
):
    if hard_delete:
        result = await conv_svc.hard_delete_conversation(conversation_id)
    else:
        result = await conv_svc.cancel_conversation(conversation_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Conversation not found"}},
        )
    return result
