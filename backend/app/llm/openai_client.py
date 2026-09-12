"""Живой провайдер поверх OpenAI-совместимого протокола.

GigaChat отличается только способом получения токена, дальше протокол тот же.
"""
import json
import time
from typing import Any

import httpx

from app.config import settings
from app.llm.client import LLMClient, note_failure, note_success, parse_json_loose
from app.llm.mock_provider import MockProvider

GIGACHAT_OAUTH = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"


class LLMError(RuntimeError):
    pass


class OpenAICompatibleProvider(LLMClient):
    name = "openai"

    def __init__(self, base_url: str | None = None, model: str | None = None,
                 flavour: str | None = None) -> None:
        self.flavour = (flavour or settings.llm_provider).lower()
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.model_name = model or settings.llm_model or "не задана"
        self.name = self.flavour
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    # --- авторизация -------------------------------------------------------

    def _bearer(self) -> str:
        if self.flavour != "gigachat":
            return settings.llm_api_key
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        response = httpx.post(
            GIGACHAT_OAUTH,
            headers={
                "Authorization": f"Basic {settings.llm_api_key}",
                "RqUID": "00000000-0000-0000-0000-000000000001",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"scope": "GIGACHAT_API_PERS"},
            timeout=settings.llm_timeout,
            verify=False,
        )
        response.raise_for_status()
        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires_at = payload.get("expires_at", 0) / 1000 or time.time() + 1500
        return self._token

    # --- низкий уровень ----------------------------------------------------

    def _post(self, payload: dict) -> dict:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._bearer()}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = httpx.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=settings.llm_timeout,
                    verify=self.flavour != "gigachat",
                )
                if response.status_code >= 500:
                    last_error = LLMError(f"Модель вернула {response.status_code}")
                    continue
                if response.status_code >= 400:
                    raise LLMError(
                        f"Модель вернула {response.status_code}: {response.text[:300]}"
                    )
                return response.json()
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
            if attempt == 0:
                time.sleep(0.6)
        raise LLMError(f"Не удалось обратиться к модели: {last_error}")

    def _fallback(self, exc: Exception, method: str, context: dict | None, *args):
        message = str(exc)
        if not settings.llm_fallback_to_mock:
            note_failure(message, fell_back=False)
            raise LLMError(message) from exc
        note_failure(message, fell_back=True)
        mock = MockProvider()
        return getattr(mock, method)(*args, context=context)

    # --- публичный интерфейс -----------------------------------------------

    def complete_json(
        self, system: str, user: str, schema: dict, context: dict[str, Any] | None = None
    ) -> tuple[dict, int]:
        system_with_schema = (
            f"{system}\n\nОтвет обязан соответствовать этой JSON-схеме:\n"
            f"{json.dumps(schema, ensure_ascii=False)}"
        )
        payload = {
            "model": self.model_name,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_with_schema},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        started = time.perf_counter()
        try:
            data = self._post(payload)
            text = data["choices"][0]["message"].get("content") or ""
            parsed = parse_json_loose(text)
            if parsed is None:
                parsed = self._repair(system_with_schema, text)
            if parsed is None:
                raise LLMError("Модель не вернула разбираемый JSON")
            note_success(self.model_name)
            return parsed, int((time.perf_counter() - started) * 1000)
        except Exception as exc:  # noqa: BLE001  падать нельзя, есть запасной путь
            result, _ = self._fallback(exc, "complete_json", context, system, user, schema)
            return result, int((time.perf_counter() - started) * 1000)

    def _repair(self, system: str, broken: str) -> dict | None:
        """Один дополнительный вызов с требованием вернуть только JSON."""
        try:
            data = self._post(
                {
                    "model": self.model_name,
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": system},
                        {
                            "role": "user",
                            "content": (
                                "Предыдущий ответ не был корректным JSON. Верни только "
                                "JSON-объект без единого лишнего символа. Вот что было:\n"
                                + broken[:3000]
                            ),
                        },
                    ],
                    "response_format": {"type": "json_object"},
                }
            )
            return parse_json_loose(data["choices"][0]["message"].get("content") or "")
        except Exception:  # noqa: BLE001
            return None

    def complete_tools(
        self, system: str, user: str, tools: list[dict], context: dict[str, Any] | None = None
    ) -> tuple[dict, int]:
        payload = {
            "model": self.model_name,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "tools": tools,
            "tool_choice": "required",
        }
        started = time.perf_counter()
        try:
            data = self._post(payload)
            message = data["choices"][0]["message"]
            calls = message.get("tool_calls") or []
            if not calls:
                raise LLMError("Модель не вызвала ни одного инструмента")
            call = calls[0]["function"]
            arguments = call.get("arguments")
            if isinstance(arguments, str):
                arguments = parse_json_loose(arguments) or {}
            note_success(self.model_name)
            return (
                {"name": call["name"], "arguments": arguments or {}},
                int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:  # noqa: BLE001
            result, _ = self._fallback(exc, "complete_tools", context, system, user, tools)
            return result, int((time.perf_counter() - started) * 1000)
