"""LLM provider settings."""

from __future__ import annotations

import os
from typing import Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # dotenv is optional; settings can still be supplied via environment variables.
    pass

try:
    # Prefer pydantic-settings (v2), then pydantic (v1). Fallback keeps module usable.
    from pydantic_settings import BaseSettings  # type: ignore
except Exception:  # pragma: no cover - fallback when pydantic isn't installed
    try:
        from pydantic import BaseSettings  # type: ignore
    except Exception:  # pragma: no cover

        class BaseSettings:  # noqa: D401 - simple fallback
            """Minimal fallback for BaseSettings when pydantic is unavailable."""

            def __init__(self, **kwargs) -> None:
                for key, value in kwargs.items():
                    setattr(self, key, value)


class LLMProviderSettings(BaseSettings):
    """Base settings for LLM providers."""

    temperature: float = 0.0
    max_tokens: Optional[int] = None
    max_retries: int = 3


# L to chat, K to generate
class OpenAISettings(LLMProviderSettings):
    """Settings for OpenAI."""

    api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    base_url: Optional[str] = os.getenv("OPENAI_BASE_URL")
    organization: Optional[str] = os.getenv("OPENAI_ORG_ID")
    default_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"


class AnthropicSettings(LLMProviderSettings):
    """Settings for Anthropic."""

    api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    base_url: Optional[str] = os.getenv("ANTHROPIC_BASE_URL")
    default_model: str = "claude-3-5-sonnet-20240620"
    max_tokens: int = 1024


class LlamaSettings(LLMProviderSettings):
    """Settings for Llama."""

    base_url: Optional[str] = os.getenv("LLAMA_BASE_URL")
    default_model: str = os.getenv("LLAMA_MODEL", "llama-3.1-8b-instruct")
    context_window: Optional[int] = None
