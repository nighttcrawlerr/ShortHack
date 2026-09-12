"""Векторные представления фрагментов. Три взаимозаменяемых источника.

gigachat — штатная модель эмбеддингов Сбера, входит в бесплатный тариф;
ollama   — локальная модель, работает без сети;
none     — эмбеддинги отключены, поиск остаётся чисто лексическим.

Ни один из режимов не является обязательным: при отсутствии векторов
поиск продолжает работать на BM25, просто чуть хуже на перефразировках.
"""
import math
import time
from typing import Sequence

import httpx

from app.config import settings


class Embedder:
    name = "none"
    dimension = 0

    def available(self) -> bool:
        return False

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        """По умолчанию запрос кодируется той же моделью, что и документы."""
        vectors = self.embed([text])
        return vectors[0] if vectors else []


class YandexEmbedder(Embedder):
    """Эмбеддинги Yandex Cloud.

    Модели для документа и для запроса разные: это несимметричный поиск,
    когда короткий вопрос и длинный фрагмент кодируются по-разному.
    На практике это заметно точнее, чем одна модель на оба случая.
    Пакетная отправка не поддерживается, тексты уходят по одному.
    """

    name = "yandex"

    def available(self) -> bool:
        return bool(
            settings.llm_api_key
            and settings.llm_folder_id
            and settings.llm_provider.lower() == "yandex"
        )

    # Сервис ограничивает частоту запросов, а тексты уходят по одному.
    # Небольшая выдержка между вызовами дешевле, чем ловить отказы и ждать
    # нарастающую паузу на каждом втором фрагменте.
    PAUSE = 0.15
    RETRIES = 4

    def _one(self, text: str, model: str) -> list[float]:
        url = f"{settings.llm_base_url.rstrip('/')}/embeddings"
        payload = {
            "model": f"emb://{settings.llm_folder_id}/{model}/latest",
            "input": [text],
        }
        headers = {
            "Authorization": f"Api-Key {settings.llm_api_key}",
            "Content-Type": "application/json",
        }

        delay = 0.5
        last: Exception | None = None
        for attempt in range(self.RETRIES):
            try:
                response = httpx.post(
                    url, headers=headers, json=payload, timeout=settings.llm_timeout
                )
                if response.status_code == 429:
                    last = RuntimeError("Превышена частота запросов к модели эмбеддингов")
                    time.sleep(delay)
                    delay *= 2
                    continue
                response.raise_for_status()
                return response.json()["data"][0]["embedding"]
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429 and attempt < self.RETRIES - 1:
                    last = exc
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last = exc
                time.sleep(delay)
                delay *= 2
        raise RuntimeError(f"Эмбеддинги недоступны: {last}")

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = []
        for index, text in enumerate(texts):
            if index:
                time.sleep(self.PAUSE)
            vectors.append(self._one(text, settings.yandex_embedding_doc))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._one(text, settings.yandex_embedding_query)


class GigaChatEmbedder(Embedder):
    name = "gigachat"

    def __init__(self, token_provider) -> None:
        self._token_provider = token_provider

    def available(self) -> bool:
        return bool(settings.llm_api_key) and settings.llm_provider.lower() == "gigachat"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        response = httpx.post(
            f"{settings.llm_base_url.rstrip('/')}/embeddings",
            headers={"Authorization": f"Bearer {self._token_provider()}"},
            json={"model": "Embeddings", "input": list(texts)},
            timeout=settings.llm_timeout,
            verify=False,
        )
        response.raise_for_status()
        payload = response.json()
        return [item["embedding"] for item in payload["data"]]


class OllamaEmbedder(Embedder):
    name = "ollama"

    def available(self) -> bool:
        try:
            response = httpx.get(f"{settings.ollama_url}/api/tags", timeout=2)
            models = [m["name"] for m in response.json().get("models", [])]
            base = settings.embedding_model.split(":")[0]
            return any(
                m == settings.embedding_model or m.split(":")[0] == base for m in models
            )
        except Exception:  # noqa: BLE001
            return False

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            response = httpx.post(
                f"{settings.ollama_url}/api/embeddings",
                json={"model": settings.embedding_model, "prompt": text},
                timeout=settings.llm_timeout,
            )
            response.raise_for_status()
            vectors.append(response.json()["embedding"])
        return vectors


def get_embedder(token_provider=None) -> Embedder:
    choice = (settings.embeddings_provider or "auto").lower()

    candidates: list[Embedder] = []
    if choice in ("auto", "yandex"):
        candidates.append(YandexEmbedder())
    if choice in ("auto", "gigachat") and token_provider is not None:
        candidates.append(GigaChatEmbedder(token_provider))
    if choice in ("auto", "ollama"):
        candidates.append(OllamaEmbedder())

    for candidate in candidates:
        try:
            if candidate.available():
                return candidate
        except Exception:  # noqa: BLE001
            continue
    return Embedder()


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if not norm_left or not norm_right:
        return 0.0
    return dot / (norm_left * norm_right)
