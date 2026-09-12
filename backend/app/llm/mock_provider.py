"""Провайдер-заглушка. Работает по ключевым словам, форма ответа как у живой модели."""
from typing import Any

from app.llm import mock_client
from app.llm.client import LLMClient


class MockProvider(LLMClient):
    name = "mock"
    model_name = "mock"

    def complete_json(
        self, system: str, user: str, schema: dict, context: dict[str, Any] | None = None
    ) -> tuple[dict, int]:
        ms = mock_client.sleep_a_little()
        ctx = context or {}
        kind = ctx.get("kind", "extract")

        if kind == "decide":
            chosen = mock_client.decide(
                ctx.get("analysis", {}),
                ctx.get("similar", []),
                ctx.get("kb", []),
                ctx.get("mass_incident", False),
            )
            return {"action": chosen["name"], "arguments": chosen["arguments"]}, ms

        return mock_client.extract(ctx.get("body", ""), ctx.get("author_name", "")), ms

    def complete_tools(
        self, system: str, user: str, tools: list[dict], context: dict[str, Any] | None = None
    ) -> tuple[dict, int]:
        ms = mock_client.sleep_a_little()
        ctx = context or {}
        return (
            mock_client.decide(
                ctx.get("analysis", {}),
                ctx.get("similar", []),
                ctx.get("kb", []),
                ctx.get("mass_incident", False),
            ),
            ms,
        )
