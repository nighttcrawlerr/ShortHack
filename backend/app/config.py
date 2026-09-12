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

    # yandex | gigachat | openai | ollama | mock
    llm_provider: str = "mock"
    llm_folder_id: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_tools: str = "auto"
    llm_timeout: int = 30
    llm_fallback_to_mock: bool = True

    # Локальная модель как запасной путь, если внешний API недоступен
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    embedding_model: str = "bge-m3"
    # У Yandex Cloud модели эмбеддингов разные для документов и запросов
    yandex_embedding_doc: str = "text-embeddings-v2-doc"
    yandex_embedding_query: str = "text-embeddings-v2-query"

    # auto | gigachat | ollama | none
    embeddings_provider: str = "auto"

    # Ответ, прошедший проверку, уходит пользователю сам. Человек подключается
    # только там, где проверка что-то нашла: он разбирает исключения,
    # а не подтверждает каждое письмо.
    auto_send: bool = True

    # Порог достоверности: ниже него ответ не показывается как готовый
    verification_threshold: float = 0.7

    # Второй слой проверки — отдельный вызов модели. Выключается,
    # если важнее скорость, чем полнота проверки.
    verify_with_model: bool = True

    database_url: str = f"sqlite:///{BACKEND_DIR / 'supportpilot.db'}"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


settings = Settings()
