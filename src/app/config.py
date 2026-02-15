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
        default="pmpt_698fd0bd177881908e6155c75caf5051054f971f90c1739f",
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
    openai_prompt_id_gate3b: str = Field(
        default="pmpt_698f91233a908193a38530bfc21a5ea307ff467d4352a6c4",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate3b",
            "OPENAI_PROMPT_ID_GATE3B",
        ),
    )
    openai_prompt_id_gate3c: str = Field(
        default="pmpt_698f91f15ed08193bf26b49690cf731a01f60e94ff8b9467",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate3c",
            "OPENAI_PROMPT_ID_GATE3C",
        ),
    )
    openai_prompt_id_gate4: str = Field(
        #default="pmpt_6977f448f57881939b6410f0541e5303004454c08c8bc19e",
        default="pmpt_698f9431c0b08193a0c301c4f992a374057cb68b291d43d1",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate4",
            "OPENAI_PROMPT_ID_GATE4",
        ),
    )
    openai_prompt_id_gate4b: str = Field(
        default="pmpt_698f94944ccc81908e741633ae70e04700504d135e320e91",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate4b",
            "OPENAI_PROMPT_ID_GATE4B",
        ),
    )
    openai_prompt_id_gate5: str = Field(
        default="pmpt_698f956ab9388194beaaf3c010f9ecba083af44f00bcb344",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate5",
            "OPENAI_PROMPT_ID_GATE5",
        ),
    )
    openai_prompt_id_gate6: str = Field(
        default="pmpt_698f96f15f748196bf6c1a302cad209a069bfe999f2a5f54",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate6",
            "OPENAI_PROMPT_ID_GATE6",
        ),
    )
    openai_prompt_id_gate7: str = Field(
        default="pmpt_698fc0af7d8481978eaea4b4f3c04f6106fb16b6264d6bfa",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate7",
            "OPENAI_PROMPT_ID_GATE7",
        ),
    )
    openai_prompt_id_gate8: str = Field(
        default="pmpt_698fc169fbac8190be759c4ef225d51e028f54ce31d56012",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate8",
            "OPENAI_PROMPT_ID_GATE8",
        ),
    )
    openai_prompt_id_gate9: str = Field(
        default="pmpt_698fc57649588193a608068866018bdc0d514a59130d9689",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate9",
            "OPENAI_PROMPT_ID_GATE9",
        ),
    )
    openai_prompt_id_gate10: str = Field(
        default="pmpt_698fc653c7888194b612a1cc0552cf510d2785432b170ae1",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate10",
            "OPENAI_PROMPT_ID_GATE10",
        ),
    )
    openai_prompt_id_gate11: str = Field(
        default="pmpt_698fc808ed68819483779236f399e4780f0556d31b05108f",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate11",
            "OPENAI_PROMPT_ID_GATE11",
        ),
    )
    openai_prompt_id_gate12: str = Field(
        default="pmpt_698fc8c63dec819795ac20deb6e6dc2e0b0ead22679c7725",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate12",
            "OPENAI_PROMPT_ID_GATE12",
        ),
    )
    openai_prompt_id_gate13: str = Field(
        default="pmpt_698fc9a974548194ab73dd8b9de548a5041fa6cb9ee62f01",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate13",
            "OPENAI_PROMPT_ID_GATE13",
        ),
    )
    openai_prompt_id_gate14: str = Field(
        default="pmpt_698fca776db0819397a781ca4f0cc09e0cbd2cff13cddf3c",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate14",
            "OPENAI_PROMPT_ID_GATE14",
        ),
    )
    openai_prompt_id_gate15: str = Field(
        default="pmpt_698fcae448608196b3a5af34e39543dd0d468eb0783e0095",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate15",
            "OPENAI_PROMPT_ID_GATE15",
        ),
    )
    openai_prompt_id_gate16: str = Field(
        default="pmpt_698fcc2efed481958d95da57eaf06a4800dd978861a335d5",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate16",
            "OPENAI_PROMPT_ID_GATE16",
        ),
    )
    openai_prompt_id_gate17: str = Field(
        default="pmpt_698fcd533ee88190a04d275ba6163e1b0a107019ab0c0e6d",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate17",
            "OPENAI_PROMPT_ID_GATE17",
        ),
    )
    openai_prompt_id_gate18: str = Field(
        default="pmpt_698fcdd1d558819690b1a1ec882cd2aa0c71bcba13f772ea",
        validation_alias=AliasChoices(
            "openai_prompt_id_gate18",
            "OPENAI_PROMPT_ID_GATE18",
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
