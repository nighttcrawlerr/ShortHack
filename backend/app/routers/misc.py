"""Служебные эндпоинты: здоровье, справочники, перезалив демо-данных."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import dictionaries as dicts
from app.db import get_db
from app.models import Message
from app.schemas import (
    HealthOut,
    KBHitOut,
    RagResponse,
    SimilarTicketOut,
    StatsOut,
)

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    from app.llm.client import llm_status

    from app.models import KBChunk
    from app.rag.retriever import Retriever

    status = llm_status()
    retriever = Retriever(db)
    return HealthOut(
        status="ok",
        llm=status["mode"],
        model=status["model"],
        llm_note=status.get("last_error"),
        retrieval=retriever.mode(),
        embedder=retriever.embedder.name,
        kb_chunks=db.query(KBChunk).count(),
        db_messages=db.query(Message).count(),
    )


@router.get("/dictionaries")
def dictionaries() -> dict:
    return dicts.as_payload()


@router.post("/seed")
def reseed(db: Session = Depends(get_db)) -> dict:
    from app.seed import seed_database

    return seed_database(db, wipe=True)


@router.get("/similar", response_model=list[SimilarTicketOut])
def similar(
    message_id: int | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
) -> list[SimilarTicketOut]:
    from app.agent.search import search_similar_tickets
    from app.models import Message

    category = service = None
    text = q or ""

    if message_id:
        message = db.get(Message, message_id)
        if message is None:
            raise HTTPException(status_code=404, detail="Обращение не найдено")
        text = f"{message.subject or ''} {message.body}"
        analysis = message.latest_analysis
        if analysis:
            category, service = analysis.category, analysis.service

    if not text.strip():
        raise HTTPException(status_code=400, detail="Нужен message_id или q")

    rows = search_similar_tickets(db, text, category, service, exclude_message_id=message_id)
    return [SimilarTicketOut(**row) for row in rows]


@router.get("/kb", response_model=list[KBHitOut])
def knowledge_base(
    q: str, category: str | None = None, db: Session = Depends(get_db)
) -> list[KBHitOut]:
    from app.agent.search import search_kb

    if not q.strip():
        raise HTTPException(status_code=400, detail="Пустой запрос")
    return [KBHitOut(**row) for row in search_kb(db, q, category)]


@router.get("/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)) -> StatsOut:
    from app.stats import build_stats

    return build_stats(db)


@router.get("/rag", response_model=RagResponse)
def rag_search(
    q: str,
    category: str | None = None,
    limit: int = 5,
    db: Session = Depends(get_db),
) -> RagResponse:
    """Прямой доступ к поиску по базе знаний. Нужен, чтобы на защите показать,
    что помощник берёт ответ из конкретных фрагментов, а не сочиняет его."""
    from app.rag.retriever import Retriever

    if not q.strip():
        raise HTTPException(status_code=400, detail="Пустой запрос")

    retriever = Retriever(db)
    hits = [p.as_dict() for p in retriever.search(q, category, limit=limit)]
    return RagResponse(
        query=q,
        mode=retriever.mode(),
        embedder=retriever.embedder.name,
        hits=hits,
    )


@router.post("/reindex")
def reindex(db: Session = Depends(get_db)) -> dict:
    """Пересобрать индекс базы знаний. Нужен после появления ключа:
    тогда к лексическому поиску добавятся векторы."""
    from app.rag.indexer import rebuild_index

    return rebuild_index(db)


@router.get("/training/corrections")
def corrections(db: Session = Depends(get_db)) -> dict:
    """Что система уже узнала от операторов."""
    from app import learning
    from app.models import Correction

    rows = db.query(Correction).order_by(Correction.id.desc()).limit(50).all()
    by_field: dict[str, int] = {}
    for row in rows:
        by_field[row.field] = by_field.get(row.field, 0) + 1

    return {
        "total": db.query(Correction).count(),
        "by_field": by_field,
        "ready_for_tuning": db.query(Correction).count() >= 500,
        "prompt_preview": learning.examples_for(db)[:1200],
        "recent": [
            {
                "field": row.field,
                "before": row.before,
                "after": row.after,
                "context": row.context[:120],
                "at": row.created_at,
            }
            for row in rows[:10]
        ],
    }


@router.get("/training/dataset.jsonl")
def dataset(db: Session = Depends(get_db)) -> Response:
    """Выгрузка для дообучения. Формат Yandex Cloud: пара запрос-ответ на строку."""
    from app import learning

    return Response(
        content=learning.dataset_jsonl(db),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="saluteagent-tuning.jsonl"'},
    )
