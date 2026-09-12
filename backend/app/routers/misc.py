"""Служебные эндпоинты: здоровье, справочники, перезалив демо-данных."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import dictionaries as dicts
from app.db import get_db
from app.models import Message
from app.schemas import HealthOut

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
