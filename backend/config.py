from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root (lead-filter-bot/) so .env works whether you run from root or backend/
_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    openai_api_key: str = "sk-your-key-here"
    openai_model: str = "gpt-4o-mini"
    database_url: str = "sqlite:///./lead_filter.db"

    model_config = SettingsConfigDict(
        env_file=str(_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
