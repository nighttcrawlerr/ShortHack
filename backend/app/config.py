"""Настройки приложения. Читаются из backend/.env."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
DATA_DIR = REPO_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "mock"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_tools: str = "auto"
    llm_timeout: int = 30
    llm_fallback_to_mock: bool = True

    database_url: str = f"sqlite:///{BACKEND_DIR / 'supportpilot.db'}"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


settings = Settings()
