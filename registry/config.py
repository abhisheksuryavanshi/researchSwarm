from enum import Enum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmbeddingProviderType(str, Enum):
    LOCAL = "local"
    GOOGLE = "google"
    OPENAI = "openai"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/researchswarm"
    )
    embedding_provider: EmbeddingProviderType = EmbeddingProviderType.LOCAL
    google_api_key: str = ""
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    log_level: str = Field(default="INFO")


settings = Settings()
