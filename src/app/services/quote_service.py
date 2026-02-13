"""Quote orchestrator: resolves gates, calls OpenAI, manages advancement."""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator

from . import conversation_service as conv_svc
from . import openai_service
from .orchestrator import orchestrator


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

    # Resolve current gate
    gate, session = await orchestrator.resolve_gate(conversation_id)
    variables = orchestrator.resolve_variables(gate, session)

    # Build history & call OpenAI
    history = await conv_svc.get_conversation_history(conversation_id)
    response_text = await openai_service.call_prompt(
        prompt_id=gate.prompt_id,
        messages=history,
        variables=variables or None,
        version=gate.prompt_version,
    )

    # Parse
    parsed = _parse_response_text(response_text)
    metadata: dict[str, Any] = {
        "prompt_id": gate.prompt_id,
        "gate_number": gate.number,
        "gate_name": gate.name,
    }
    if parsed and isinstance(parsed, dict):
        metadata["parsed_status"] = parsed.get("status")

    # Check advancement
    if orchestrator.should_advance(parsed):
        new_gate_num = await orchestrator.advance_gate(conversation_id, session, parsed)
        metadata["advanced_to_gate"] = new_gate_num

        # Auto-fetch the next gate's first question
        if new_gate_num is not None:
            try:
                next_gate, next_session = await orchestrator.resolve_gate(conversation_id)
                next_variables = orchestrator.resolve_variables(next_gate, next_session)
                next_history = await conv_svc.get_conversation_history(conversation_id)
                next_response_text = await openai_service.call_prompt(
                    prompt_id=next_gate.prompt_id,
                    messages=next_history,
                    variables=next_variables or None,
                    version=next_gate.prompt_version,
                )
                next_parsed = _parse_response_text(next_response_text)
                metadata["next_gate"] = {
                    "gate_number": next_gate.number,
                    "gate_name": next_gate.name,
                    "response": next_parsed or next_response_text,
                }
            except Exception as e:
                metadata["next_gate_error"] = str(e)
    else:
        await orchestrator.save_session(conversation_id, session)

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

    # Resolve current gate
    gate, session = await orchestrator.resolve_gate(conversation_id)
    variables = orchestrator.resolve_variables(gate, session)

    # Build history
    history = await conv_svc.get_conversation_history(conversation_id)

    chunks: list[str] = []

    async for delta in openai_service.stream_prompt(
        prompt_id=gate.prompt_id,
        messages=history,
        variables=variables or None,
        version=gate.prompt_version,
    ):
        chunks.append(delta)
        yield {"type": "chunk", "delta": delta}

    full_text = "".join(chunks).strip()
    parsed = _parse_response_text(full_text)
    metadata: dict[str, Any] = {
        "prompt_id": gate.prompt_id,
        "gate_number": gate.number,
        "gate_name": gate.name,
    }
    if parsed and isinstance(parsed, dict):
        metadata["parsed_status"] = parsed.get("status")

    # Check advancement
    if orchestrator.should_advance(parsed):
        new_gate_num = await orchestrator.advance_gate(conversation_id, session, parsed)
        metadata["advanced_to_gate"] = new_gate_num

        # Auto-fetch the next gate's first question
        if new_gate_num is not None:
            try:
                next_gate, next_session = await orchestrator.resolve_gate(conversation_id)
                next_variables = orchestrator.resolve_variables(next_gate, next_session)
                next_history = await conv_svc.get_conversation_history(conversation_id)
                next_response_text = await openai_service.call_prompt(
                    prompt_id=next_gate.prompt_id,
                    messages=next_history,
                    variables=next_variables or None,
                    version=next_gate.prompt_version,
                )
                next_parsed = _parse_response_text(next_response_text)
                metadata["next_gate"] = {
                    "gate_number": next_gate.number,
                    "gate_name": next_gate.name,
                    "response": next_parsed or next_response_text,
                }
            except Exception as e:
                metadata["next_gate_error"] = str(e)
    else:
        await orchestrator.save_session(conversation_id, session)

    # Store assistant message
    msg = await conv_svc.add_message(
        conversation_id,
        "assistant",
        full_text,
        response_json=parsed,
        metadata_json=metadata,
    )

    yield {"type": "done", "message": msg}
