from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    Defines foundational configuration such as database URL and logging level.
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = (
        "mysql+aiomysql://root:root@localhost:3306/researchswarm"
    )
    log_level: str = Field(default="INFO")
    log_directory: str = Field(
        default="logs",
        description="Directory for backend.jsonl; relative to cwd unless absolute.",
    )
    cors_origins: str = Field(
        default=(
            "http://localhost:5173,http://127.0.0.1:5173,"
            "http://localhost:4173,http://127.0.0.1:4173"
        ),
        description="Comma-separated allowed browser origins for CORS.",
    )


settings = Settings()
