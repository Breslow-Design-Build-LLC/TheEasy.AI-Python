"""Thin wrapper around the OpenAI Prompts / Responses API.

Uses the *sync* OpenAI client (matching Step1.py / Step2.py patterns) and
runs blocking calls via ``asyncio.get_event_loop().run_in_executor`` so we
don't block the FastAPI event loop.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator, Optional

from openai import OpenAI

from ..config import settings


def _build_client() -> OpenAI:
    return OpenAI(api_key=settings.resolved_api_key)


_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def _call_prompt_sync(
    prompt_id: str,
    messages: list[dict[str, str]],
    variables: dict[str, str] | None = None,
    version: str | None = None,
) -> str:
    """Synchronous call to OpenAI Prompts API. Returns the output text."""
    client = get_client()
    prompt_payload: dict[str, Any] = {"id": prompt_id}
    # if version:
    #     prompt_payload["version"] = version
    prompt_payload["variables"] = variables or {}

    response = client.responses.create(
        prompt=prompt_payload,
        input=messages,
        stream=False,
        store=True,
    )
    return response.output_text


async def call_prompt(
    prompt_id: str,
    messages: list[dict[str, str]],
    variables: dict[str, str] | None = None,
    version: str | None = None,
) -> str:
    """Async wrapper: run the sync OpenAI call in a thread executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        _call_prompt_sync,
        prompt_id,
        messages,
        variables,
        version,
    )


def _stream_prompt_sync(
    prompt_id: str,
    messages: list[dict[str, str]],
    variables: dict[str, str] | None = None,
    version: str | None = None,
):
    """Synchronous generator that yields text deltas from OpenAI streaming."""
    client = get_client()
    prompt_payload: dict[str, Any] = {"id": prompt_id}
    # if version:
    #     prompt_payload["version"] = version
    prompt_payload["variables"] = variables or {}

    stream = client.responses.create(
        prompt=prompt_payload,
        input=messages,
        stream=True,
    )
    for event in stream:
        if event.type == "response.output_text.delta":
            yield event.delta


async def stream_prompt(
    prompt_id: str,
    messages: list[dict[str, str]],
    variables: dict[str, str] | None = None,
    version: str | None = None,
) -> AsyncGenerator[str, None]:
    """Async generator that yields text deltas by running the sync stream in a thread."""
    import queue
    import threading

    q: queue.Queue[str | None] = queue.Queue()

    def _producer():
        try:
            for delta in _stream_prompt_sync(prompt_id, messages, variables, version):
                q.put(delta)
        finally:
            q.put(None)  # sentinel

    thread = threading.Thread(target=_producer, daemon=True)
    thread.start()

    loop = asyncio.get_event_loop()
    while True:
        item = await loop.run_in_executor(None, q.get)
        if item is None:
            break
        yield item
