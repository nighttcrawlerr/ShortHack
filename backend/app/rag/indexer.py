"""Построение индекса: статьи -> фрагменты -> токены -> векторы."""
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import KBArticle, KBChunk
from app.rag.chunker import split_article
from app.rag.embeddings import get_embedder
from app.rag.retriever import Retriever
from app.rag.tokens import tokenize

BATCH = 16


def rebuild_index(db: Session, token_provider=None, with_vectors: bool = True) -> dict:
    db.execute(delete(KBChunk))
    db.commit()

    created: list[KBChunk] = []
    for article in db.query(KBArticle).order_by(KBArticle.id).all():
        # Заголовок и ключевые слова статьи попадают в индекс дополнительно:
        # совпадение по теме статьи должно весить больше, чем случайное
        # совпадение по слову из середины текста.
        # Ключевые слова — прямое указание автора статьи, о чём она.
        # Даём им двойной вес, заголовку одинарный.
        boost = tokenize(article.title) + 2 * tokenize(" ".join(article.keywords or []))
        for ordinal, text in enumerate(split_article(article.title, article.body)):
            chunk = KBChunk(
                article_id=article.id,
                ordinal=ordinal,
                title=article.title,
                text=text,
                category=article.category,
                service=article.service,
                source=article.source or "",
                tokens=tokenize(text) + boost,
            )
            db.add(chunk)
            created.append(chunk)
    db.commit()

    embedder = get_embedder(token_provider)
    embedded = 0
    error: str | None = None

    if with_vectors and embedder.available() and created:
        for start in range(0, len(created), BATCH):
            batch = created[start : start + BATCH]
            try:
                vectors = embedder.embed([chunk.text for chunk in batch])
            except Exception as exc:  # noqa: BLE001  индекс полезен и без векторов
                # Молча проглотить ошибку нельзя: иначе поиск тихо деградирует
                # до лексического, и никто этого не заметит до самой защиты.
                error = f"{type(exc).__name__}: {exc}"[:300]
                break
            for chunk, vector in zip(batch, vectors):
                chunk.embedding = vector
                chunk.embedder = embedder.name
                embedded += 1
            db.commit()

    Retriever._cache = {}
    result = {
        "chunks": len(created),
        "embedded": embedded,
        "embedder": embedder.name,
    }
    if error:
        result["error"] = error
    return result


def fill_vectors_in_background() -> None:
    """Досчитывает векторы после запуска приложения.

    Считать их на старте нельзя: каждый фрагмент уходит отдельным запросом,
    и приложение молчит все эти секунды. Лексический поиск работает сразу,
    векторный подключается через несколько секунд после запуска.
    """
    import threading

    def worker() -> None:
        from app.db import SessionLocal
        from app.models import KBChunk

        db = SessionLocal()
        try:
            pending = db.query(KBChunk).filter(KBChunk.embedding.is_(None)).count()
            if not pending:
                return
            embedder = get_embedder()
            if not embedder.available():
                return
            rebuild_index(db, with_vectors=True)
        except Exception:  # noqa: BLE001  фоновая задача не должна ронять сервис
            pass
        finally:
            db.close()

    threading.Thread(target=worker, daemon=True, name="fill-vectors").start()
