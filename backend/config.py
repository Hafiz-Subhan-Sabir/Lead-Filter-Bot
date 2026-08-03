from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parent.parent
_DB_PATH = _ROOT / "lead_filter.db"


class Settings(BaseSettings):
    openai_api_key: str = "sk-your-key-here"
    openai_model: str = "gpt-4o-mini"
    database_url: str = f"sqlite:///{_DB_PATH.as_posix()}"
    # Optional: better discovery than free DuckDuckGo
    brave_api_key: str = ""
    serpapi_key: str = ""
    discover_max_results: int = 12

    model_config = SettingsConfigDict(
        env_file=str(_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
