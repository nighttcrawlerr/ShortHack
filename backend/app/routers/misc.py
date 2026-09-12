"""Служебные эндпоинты: здоровье, справочники, перезалив демо-данных."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import dictionaries as dicts
from app.db import get_db
from app.models import Message
from app.schemas import HealthOut, KBHitOut, SimilarTicketOut, StatsOut

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    from app.llm.client import llm_status

    status = llm_status()
    return HealthOut(
        status="ok",
        llm=status["mode"],
        model=status["model"],
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
