"""Гибридный поиск по базе знаний.

Лексический BM25 и векторная близость дают разные ошибки: первый не понимает
перефразировок, второй теряет точные коды ошибок и артикулы. Списки объединяем
взаимно-ранговым слиянием, которое не требует приводить несравнимые оценки
к общей шкале.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models import KBChunk
from app.rag.bm25 import BM25
from app.rag.embeddings import Embedder, cosine, get_embedder
from app.rag.tokens import tokenize

RRF_K = 60
CATEGORY_BONUS = 0.05
TOP_LEXICAL = 12
TOP_DENSE = 12


@dataclass
class Passage:
    chunk_id: int
    article_id: int
    title: str
    text: str
    category: str
    service: str
    source: str
    score: float
    lexical_rank: int | None = None
    dense_rank: int | None = None
    matched_terms: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "article_id": self.article_id,
            "title": self.title,
            "text": self.text,
            "category": self.category,
            "service": self.service,
            "source": self.source,
            "score": round(self.score, 4),
            "lexical_rank": self.lexical_rank,
            "dense_rank": self.dense_rank,
            "matched_terms": self.matched_terms[:8],
        }


class Retriever:
    """Индекс строится в памяти при первом обращении и переживает запросы."""

    _cache: dict[str, object] = {}

    def __init__(self, db: Session, embedder: Embedder | None = None) -> None:
        self.db = db
        self.embedder = embedder or get_embedder()

    def _load(self) -> tuple[list[KBChunk], BM25]:
        chunks = self.db.query(KBChunk).order_by(KBChunk.id).all()
        signature = f"{len(chunks)}:{chunks[-1].id if chunks else 0}"
        if self._cache.get("signature") != signature:
            corpus = [chunk.tokens or tokenize(chunk.text) for chunk in chunks]
            Retriever._cache = {"signature": signature, "bm25": BM25(corpus)}
        return chunks, self._cache["bm25"]  # type: ignore[return-value]

    def search(
        self, query: str, category: str | None = None, limit: int = 4
    ) -> list[Passage]:
        chunks, bm25 = self._load()
        if not chunks:
            return []

        query_terms = tokenize(query)
        lexical = bm25.rank(query_terms)[:TOP_LEXICAL]

        dense: list[tuple[int, float]] = []
        query_vector: list[float] = []
        if self.embedder.available():
            try:
                query_vector = self.embedder.embed([query])[0]
            except Exception:  # noqa: BLE001  поиск обязан работать и без векторов
                query_vector = []
        if query_vector:
            scored = [
                (index, cosine(query_vector, chunk.embedding or []))
                for index, chunk in enumerate(chunks)
            ]
            scored = [pair for pair in scored if pair[1] > 0.15]
            scored.sort(key=lambda pair: pair[1], reverse=True)
            dense = scored[:TOP_DENSE]

        fused: dict[int, float] = {}
        lexical_rank: dict[int, int] = {}
        dense_rank: dict[int, int] = {}
        raw: dict[int, float] = {}

        lexical_best = lexical[0][1] if lexical else 0.0
        dense_best = dense[0][1] if dense else 0.0

        for position, (index, score) in enumerate(lexical, start=1):
            fused[index] = fused.get(index, 0.0) + 1 / (RRF_K + position)
            lexical_rank[index] = position
            if lexical_best:
                raw[index] = max(raw.get(index, 0.0), score / lexical_best)
        for position, (index, score) in enumerate(dense, start=1):
            fused[index] = fused.get(index, 0.0) + 1 / (RRF_K + position)
            dense_rank[index] = position
            if dense_best:
                raw[index] = max(raw.get(index, 0.0), score / dense_best)

        if category:
            for index in list(fused):
                if chunks[index].category == category:
                    fused[index] += CATEGORY_BONUS * (1 / RRF_K)

        ordered = sorted(fused.items(), key=lambda pair: pair[1], reverse=True)[:limit]
        if not ordered:
            return []

        query_set = set(query_terms)

        passages = []
        for index, score in ordered:
            chunk = chunks[index]
            passages.append(
                Passage(
                    chunk_id=chunk.id,
                    article_id=chunk.article_id,
                    title=chunk.title,
                    text=chunk.text,
                    category=chunk.category,
                    service=chunk.service,
                    source=chunk.source,
                    score=raw.get(index, 0.0),
                    lexical_rank=lexical_rank.get(index),
                    dense_rank=dense_rank.get(index),
                    matched_terms=sorted(query_set & set(chunk.tokens or [])),
                )
            )
        return passages

    def mode(self) -> str:
        return "гибридный" if self.embedder.available() else "лексический"
