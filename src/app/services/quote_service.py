"""Quote orchestrator: decides which prompt step to use, parses responses."""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Optional

from ..config import settings
from . import conversation_service as conv_svc
from . import openai_service


def _pick_prompt(
    conversation_history: list[dict[str, str]],
) -> tuple[str, dict[str, str] | None, str | None]:
    """Choose the correct prompt ID, variables, and version based on conversation state.

    - First user message -> Step 1 (product selection) with product_options variable + version
    - Subsequent messages -> Step 2 (detailed quoting), no version (matches Step2.py)
    """
    user_messages = [m for m in conversation_history if m["role"] == "user"]
    if len(user_messages) <= 1:
        return (
            settings.openai_prompt_id_step1,
            {"product_options": settings.product_options},
            settings.openai_prompt_version,
        )
    return settings.openai_prompt_id_step2, {}, None


def _parse_response_text(text: str) -> dict[str, Any] | None:
    """Try to parse the response as JSON; return None if it's plain text."""
    text = text.strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


async def handle_message(
    conversation_id: str,
    user_message: str,
) -> dict[str, Any]:
    """Process a user message: store it, call OpenAI, store + return assistant reply."""
    # Store user message
    await conv_svc.add_message(conversation_id, "user", user_message)

    # Build history & pick prompt
    history = await conv_svc.get_conversation_history(conversation_id)
    prompt_id, variables, version = _pick_prompt(history)

    # Call OpenAI
    response_text = await openai_service.call_prompt(
        prompt_id=prompt_id,
        messages=history,
        variables=variables,
        version=version,
    )

    # Parse
    parsed = _parse_response_text(response_text)
    metadata = {"prompt_id": prompt_id}
    if parsed and isinstance(parsed, dict):
        metadata["parsed_status"] = parsed.get("status")

    # Store assistant message
    msg = await conv_svc.add_message(
        conversation_id,
        "assistant",
        response_text,
        response_json=parsed,
        metadata_json=metadata,
    )

    return msg


async def handle_message_stream(
    conversation_id: str,
    user_message: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream version: yields dicts with type='chunk' or type='done'."""
    # Store user message
    await conv_svc.add_message(conversation_id, "user", user_message)

    # Build history & pick prompt
    history = await conv_svc.get_conversation_history(conversation_id)
    prompt_id, variables, version = _pick_prompt(history)

    chunks: list[str] = []

    async for delta in openai_service.stream_prompt(
        prompt_id=prompt_id,
        messages=history,
        variables=variables,
        version=version,
    ):
        chunks.append(delta)
        yield {"type": "chunk", "delta": delta}

    full_text = "".join(chunks).strip()
    parsed = _parse_response_text(full_text)
    metadata = {"prompt_id": prompt_id}
    if parsed and isinstance(parsed, dict):
        metadata["parsed_status"] = parsed.get("status")

    # Store assistant message
    msg = await conv_svc.add_message(
        conversation_id,
        "assistant",
        full_text,
        response_json=parsed,
        metadata_json=metadata,
    )

    yield {"type": "done", "message": msg}
