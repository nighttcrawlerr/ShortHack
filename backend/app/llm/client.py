"""Выбор провайдера модели, разбор нестрогого JSON, состояние для /api/health."""
import json
import re
from typing import Any

from app.config import settings

_state: dict[str, Any] = {"mode": None, "model": None, "last_error": None}


def parse_json_loose(text: str) -> dict | None:
    """Разбирает JSON, даже если модель обернула его в пояснения или markdown."""
    if not text:
        return None

    candidates = [text.strip()]

    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, flags=re.DOTALL)
    if fenced:
        candidates.append(fenced.group(1).strip())

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


class LLMClient:
    """Общий интерфейс. Реализации возвращают кортеж (результат, миллисекунды)."""

    name = "base"

    model_name = "base"

    def complete_json(
        self, system: str, user: str, schema: dict, context: dict[str, Any] | None = None
    ) -> tuple[dict, int]:
        """context нужен только заглушке, живой провайдер его игнорирует."""
        raise NotImplementedError

    def complete_tools(
        self, system: str, user: str, tools: list[dict], context: dict[str, Any] | None = None
    ) -> tuple[dict, int]:
        raise NotImplementedError


def _mock_reason() -> str:
    if settings.llm_provider == "mock":
        return "Провайдер переключён на заглушку в настройках"
    if not settings.llm_api_key:
        return "Не задан LLM_API_KEY"
    if not settings.llm_base_url:
        return "Не задан LLM_BASE_URL"
    return "Живой провайдер недоступен"


def get_llm_client() -> LLMClient:
    from app.llm.mock_provider import MockProvider

    provider = (settings.llm_provider or "mock").lower()
    ready = bool(settings.llm_api_key and settings.llm_base_url)

    if provider in ("openai", "gigachat") and ready:
        from app.llm.openai_client import OpenAICompatibleProvider

        return OpenAICompatibleProvider()

    _state["mode"] = "mock"
    _state["model"] = "mock"
    _state["last_error"] = _mock_reason()
    return MockProvider()


def note_success(model: str) -> None:
    _state["mode"] = "live"
    _state["model"] = model
    _state["last_error"] = None


def note_failure(error: str, fell_back: bool) -> None:
    _state["mode"] = "mock" if fell_back else "error"
    _state["model"] = "mock" if fell_back else (settings.llm_model or "не задана")
    _state["last_error"] = error


def llm_status() -> dict:
    if _state["mode"] is None:
        provider = (settings.llm_provider or "mock").lower()
        ready = bool(settings.llm_api_key and settings.llm_base_url)
        if provider in ("openai", "gigachat") and ready:
            return {
                "mode": "live",
                "model": settings.llm_model or "не задана",
                "last_error": None,
            }
        return {"mode": "mock", "model": "mock", "last_error": _mock_reason()}
    return dict(_state)
