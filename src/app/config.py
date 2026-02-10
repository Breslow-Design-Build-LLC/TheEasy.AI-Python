"""Application settings loaded from environment variables."""

from __future__ import annotations

from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class AppSettings(BaseSettings):
    """Central configuration for the QuoteApp API."""

    # Auth
    bearer_token: str = "changeme"

    # OpenAI
    api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_prompt_id_step1: str = "pmpt_6977d1cf2b208195b83507388f431b30072ae8d30040d02c"
    openai_prompt_id_step2: str = "pmpt_6977e7418e708193ba722b4422464f080876845b508020c9"
    openai_prompt_version: str = "5"

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # Database
    database_url: str = "data/quoteapp.db"

    # Product options fed to Step 1 prompt
    product_options: str = (
        "A) R-Blade\n"
        "B) R-Breeze\n"
        "C) K-Bana\n"
        "D) X-Blast\n"
        "E) Sky-Tilt"
    )

    @property
    def resolved_api_key(self) -> str:
        """Return whichever OpenAI key is set (API_KEY takes precedence)."""
        return self.api_key or self.openai_api_key or ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = AppSettings()
