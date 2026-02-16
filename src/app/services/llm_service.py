"""Multi-provider LLM service — unified interface for OpenAI + Anthropic.

Resolves which provider to use based on llm_models.provider, then routes
the call to the appropriate SDK.  Returns a standardized LLMResponse.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Optional

from ..config import settings

# ── Response dataclass ────────────────────────────────────────────────────────

@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    model_used: str
    provider: str


# ── Provider clients (lazy singletons) ────────────────────────────────────────

_openai_client = None
_anthropic_client = None


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=settings.resolved_api_key)
    return _openai_client


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def call_llm(
    model_id: str,
    provider: str,
    messages: list[dict[str, str]],
    system_prompt: str = "",
    temperature: float = 0.0,
    max_tokens: int = 16384,
    json_mode: bool = True,
) -> LLMResponse:
    """Call an LLM and return a standardized response.

    Args:
        model_id:      API model string, e.g. "gpt-4.1", "claude-sonnet-4"
        provider:      "openai" or "anthropic"
        messages:      Chat messages [{role, content}, ...]
        system_prompt: System/instructions prompt
        temperature:   Sampling temperature
        max_tokens:    Max output tokens
        json_mode:     Request JSON output (provider-specific handling)

    Returns:
        LLMResponse with content, token counts, latency, model info
    """
    start = time.perf_counter()

    if provider == "openai":
        result = _call_openai(model_id, messages, system_prompt, temperature, max_tokens, json_mode)
    elif provider == "anthropic":
        result = _call_anthropic(model_id, messages, system_prompt, temperature, max_tokens, json_mode)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    result.latency_ms = elapsed_ms
    return result


def call_llm_stream(
    model_id: str,
    provider: str,
    messages: list[dict[str, str]],
    system_prompt: str = "",
    temperature: float = 0.0,
    max_tokens: int = 16384,
    json_mode: bool = True,
):
    """Stream an LLM response, yielding text deltas.

    Yields:
        str chunks of the response as they arrive

    Returns after the stream completes.
    """
    if provider == "openai":
        yield from _stream_openai(model_id, messages, system_prompt, temperature, max_tokens, json_mode)
    elif provider == "anthropic":
        yield from _stream_anthropic(model_id, messages, system_prompt, temperature, max_tokens)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


# ═══════════════════════════════════════════════════════════════════════════════
# OpenAI Implementation
# ═══════════════════════════════════════════════════════════════════════════════

def _call_openai(
    model_id: str,
    messages: list[dict[str, str]],
    system_prompt: str,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> LLMResponse:
    """Call OpenAI Responses API (or Chat Completions as fallback)."""
    client = _get_openai_client()

    try:
        # Try Responses API first (preferred for gpt-4.1+)
        resp = client.responses.create(
            model=model_id,
            instructions=system_prompt,
            input=messages,
            temperature=temperature,
            max_output_tokens=max_tokens,
            text={"format": {"type": "json_object"}} if json_mode else None,
        )
        content = resp.output_text or ""
        input_tokens = getattr(resp.usage, "input_tokens", 0)
        output_tokens = getattr(resp.usage, "output_tokens", 0)
    except Exception:
        # Fallback to Chat Completions
        chat_messages = []
        if system_prompt:
            chat_messages.append({"role": "system", "content": system_prompt})
        chat_messages.extend(messages)

        kwargs: dict[str, Any] = {
            "model": model_id,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        content = choice.message.content or ""
        input_tokens = resp.usage.prompt_tokens if resp.usage else 0
        output_tokens = resp.usage.completion_tokens if resp.usage else 0

    return LLMResponse(
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=0,  # set by caller
        model_used=model_id,
        provider="openai",
    )


def _stream_openai(
    model_id: str,
    messages: list[dict[str, str]],
    system_prompt: str,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
):
    """Stream from OpenAI Chat Completions API."""
    client = _get_openai_client()

    chat_messages = []
    if system_prompt:
        chat_messages.append({"role": "system", "content": system_prompt})
    chat_messages.extend(messages)

    kwargs: dict[str, Any] = {
        "model": model_id,
        "messages": chat_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    stream = client.chat.completions.create(**kwargs)
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


# ═══════════════════════════════════════════════════════════════════════════════
# Anthropic Implementation
# ═══════════════════════════════════════════════════════════════════════════════

def _call_anthropic(
    model_id: str,
    messages: list[dict[str, str]],
    system_prompt: str,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> LLMResponse:
    """Call Anthropic Messages API."""
    client = _get_anthropic_client()

    # Anthropic expects system as a top-level parameter, not in messages
    # Also filter out any system messages from the messages list
    filtered = [m for m in messages if m.get("role") != "system"]

    # If json_mode, append instruction to system prompt
    sys_prompt = system_prompt
    if json_mode:
        sys_prompt += "\n\nIMPORTANT: Respond with valid JSON only. No markdown, no extra text."

    resp = client.messages.create(
        model=model_id,
        system=sys_prompt,
        messages=filtered,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = resp.content[0].text if resp.content else ""
    return LLMResponse(
        content=content,
        input_tokens=resp.usage.input_tokens if resp.usage else 0,
        output_tokens=resp.usage.output_tokens if resp.usage else 0,
        latency_ms=0,
        model_used=model_id,
        provider="anthropic",
    )


def _stream_anthropic(
    model_id: str,
    messages: list[dict[str, str]],
    system_prompt: str,
    temperature: float,
    max_tokens: int,
):
    """Stream from Anthropic Messages API."""
    client = _get_anthropic_client()
    filtered = [m for m in messages if m.get("role") != "system"]

    with client.messages.stream(
        model=model_id,
        system=system_prompt,
        messages=filtered,
        temperature=temperature,
        max_tokens=max_tokens,
    ) as stream:
        for text in stream.text_stream:
            yield text
