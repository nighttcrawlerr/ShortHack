"""Векторные представления фрагментов. Три взаимозаменяемых источника.

gigachat — штатная модель эмбеддингов Сбера, входит в бесплатный тариф;
ollama   — локальная модель, работает без сети;
none     — эмбеддинги отключены, поиск остаётся чисто лексическим.

Ни один из режимов не является обязательным: при отсутствии векторов
поиск продолжает работать на BM25, просто чуть хуже на перефразировках.
"""
import math
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
