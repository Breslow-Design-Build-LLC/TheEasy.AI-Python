"""Application settings loaded from environment variables."""

from __future__ import annotations

from typing import Optional

from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings

load_dotenv()


class AppSettings(BaseSettings):
    """Central configuration for the QuoteApp API."""

    # Auth
    bearer_token: str = "changeme"

    # OpenAI
    api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_prompt_id_gate1: str = Field(
        default="pmpt_6977d1cf2b208195b83507388f431b30072ae8d30040d02c",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate1",
            "OPENAI_PROMPT_ID_GATE1",
            "openai_prompt_id_step1",
            "OPENAI_PROMPT_ID_STEP1",
        ),
    )
    openai_prompt_id_gate2: str = Field(
        #default="pmpt_6977e7418e708193ba722b4422464f080876845b508020c9",
        default="pmpt_698f24734b2c8190b35dbd645766daba0a00ac37516c9940",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate2",
            "OPENAI_PROMPT_ID_GATE2",
            "openai_prompt_id_step2",
            "OPENAI_PROMPT_ID_STEP2",
        ),
    )
    openai_prompt_id_gate2b: str = Field(
        default="pmpt_698f2e84a3a4819692fe9ba63dacfe53057c8a385232b3fd",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate2b",
            "OPENAI_PROMPT_ID_GATE2B",
        ),
    )
    openai_prompt_id_gate3: str = Field(
        default="pmpt_698f31a4830881958384594286c8c62f06c5a37e85bd4e6b",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate3",
            "OPENAI_PROMPT_ID_GATE3",
        ),
    )
    openai_prompt_id_gate4: str = Field(
        #default="pmpt_6977f448f57881939b6410f0541e5303004454c08c8bc19e",
        default="pmpt_6977f448f57881939b6410f0541e5303004454c08c8bc19e",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate4",
            "OPENAI_PROMPT_ID_GATE4",
        ),
    )
    openai_prompt_id_gate5: str = Field(
        default="pmpt_6977f7ad484c819795d265ad1bf07b930402ff510a9eb765",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate5",
            "OPENAI_PROMPT_ID_GATE5",
        ),
    )
    openai_prompt_id_gate6: str = Field(
        default="pmpt_697803e1e5e0819587867faccf71fa6409cf1cc966d5e321",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate6",
            "OPENAI_PROMPT_ID_GATE6",
        ),
    )
    openai_prompt_id_gate7: str = Field(
        default="pmpt_697805fb59588196a446eb48e392548109820f5362547ca4",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate7",
            "OPENAI_PROMPT_ID_GATE7",
        ),
    )
    openai_prompt_id_gate8: str = Field(
        default="pmpt_6978071466bc8190a15ee761a83398410b726c8acef309cc",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate8",
            "OPENAI_PROMPT_ID_GATE8",
        ),
    )
    openai_prompt_id_gate9: str = Field(
        default="pmpt_697807cb96fc8194b82b82fce26f21bf09a1fc92e4563c30",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate9",
            "OPENAI_PROMPT_ID_GATE9",
        ),
    )
    openai_prompt_id_gate10: str = Field(
        default="pmpt_6978092468cc81958ff5aae5ad2b5b9c0b95329c9d220ede",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate10",
            "OPENAI_PROMPT_ID_GATE10",
        ),
    )
    openai_prompt_id_gate11: str = Field(
        default="pmpt_697809f6c66081958a4aacfe7e704d3f02d00efa02c8f61b",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate11",
            "OPENAI_PROMPT_ID_GATE11",
        ),
    )
    openai_prompt_id_gate12: str = Field(
        default="pmpt_69780a90ce6881969d905471a1ad83a505416370ca27f5bb",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate12",
            "OPENAI_PROMPT_ID_GATE12",
        ),
    )
    openai_prompt_id_gate13: str = Field(
        default="pmpt_69780bc3d80c819396ff8278323c3193080e758869de286b",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate13",
            "OPENAI_PROMPT_ID_GATE13",
        ),
    )
    openai_prompt_id_gate14: str = Field(
        default="pmpt_6978110a94ec8194b17002c5ade3afd70bacd06984cffa57",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate14",
            "OPENAI_PROMPT_ID_GATE14",
        ),
    )
    openai_prompt_id_gate15: str = Field(
        default="pmpt_697811b7f65881958e5a4f89b62b705f04088f60550ae728",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate15",
            "OPENAI_PROMPT_ID_GATE15",
        ),
    )
    openai_prompt_id_gate16: str = Field(
        default="pmpt_6978126bfc1081909f6b9f79fb54a2c802d66271fdf751e6",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate16",
            "OPENAI_PROMPT_ID_GATE16",
        ),
    )
    openai_prompt_version: str = "5"

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # Database
    database_url: str = "data/quoteapp.db"

    # Product options fed to Gate 1 prompt
    product_options: str = (
        "A) R-Blade\nB) R-Breeze\nC) K-Bana\nD) X-Blast\nE) Sky-Tilt\nF) Kitchens"
    )

    # Dimension context fed to Gate 2 prompt (R-Blade rules)
    dimension_context: str = (
        '{"PRODUCT_ID":"r_blade",'
        '"DIMENSION_RULES":{"r_blade":{'
        '"rounding_method":"ceil",'
        '"rounding_increment_ft":1,'
        '"max_width_single_bay_ft":16,'
        '"max_length_single_bay_ft":23'
        '}}}'
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
