from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parent.parent
_DB_PATH = _ROOT / "lead_filter.db"


class Settings(BaseSettings):
    openai_api_key: str = "sk-your-key-here"
    openai_model: str = "gpt-4o-mini"
    database_url: str = f"sqlite:///{_DB_PATH.as_posix()}"
    brave_api_key: str = ""
    serpapi_key: str = ""
    # Deep search defaults (multi-pass, ~3–5 minutes)
    discover_max_results: int = 40
    discover_queries_per_platform: int = 3
    discover_pause_seconds: float = 8.0
    discover_min_genuine: float = 55.0

    model_config = SettingsConfigDict(
        env_file=str(_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
