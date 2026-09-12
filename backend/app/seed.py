"""Загрузка демонстрационных данных из data/*.json."""
import json
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import DATA_DIR
from app.models import AgentStep, Analysis, KBArticle, Message, Outbox, Ticket, now_iso

MESSAGES_FILE = DATA_DIR / "seed_messages.json"
KB_FILE = DATA_DIR / "kb_articles.json"


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _shift_to_today(raw_messages: list[dict]) -> list[str]:
    """Сдвигает времена обращений так, чтобы самое свежее пришло пять минут назад.

    Промежутки между обращениями сохраняются. Без этого демонстрация ломается
    на следующий день: признак массового сбоя смотрит на последние шесть часов.
    """
    parsed = [datetime.fromisoformat(m["received_at"]) for m in raw_messages]
    newest = max(parsed)
    target = datetime.now().replace(microsecond=0) - timedelta(minutes=5)
    shift = target - newest
    return [(dt + shift).isoformat() for dt in parsed]


def seed_database(db: Session, wipe: bool = True) -> dict:
    if wipe:
        for model in (AgentStep, Outbox, Analysis, Ticket, KBArticle, Message):
            db.execute(delete(model))
        db.commit()

    payload = _read(MESSAGES_FILE)
    raw_messages = payload["messages"]
    raw_tickets = payload.get("closed_tickets", [])
    raw_kb = _read(KB_FILE)

    received = _shift_to_today(raw_messages)

    for raw, received_at in zip(raw_messages, received):
        db.add(
            Message(
                channel=raw.get("channel", "email"),
                subject=raw.get("subject"),
                author_name=raw.get("author_name", ""),
                author_email=raw.get("author_email", ""),
                received_at=received_at,
                body=raw.get("body", ""),
                status="new",
                created_at=now_iso(),
            )
        )

    for raw in raw_tickets:
        db.add(
            Ticket(
                key=raw["key"],
                message_id=None,
                title=raw.get("title", ""),
                description=raw.get("description", ""),
                category=raw.get("category", "other"),
                service=raw.get("service", ""),
                priority=raw.get("priority", "P3"),
                team=raw.get("team", "l1_support"),
                status="closed",
                requester_name=raw.get("requester_name", ""),
                requester_email=raw.get("requester_email", ""),
                entities={},
                resolution=raw.get("resolution"),
                created_by="operator",
            )
        )

    for raw in raw_kb:
        db.add(
            KBArticle(
                title=raw.get("title", ""),
                category=raw.get("category", "other"),
                service=raw.get("service", ""),
                keywords=raw.get("keywords", []),
                body=raw.get("body", ""),
            )
        )

    db.commit()
    return {
        "messages": len(raw_messages),
        "kb_articles": len(raw_kb),
        "tickets": len(raw_tickets),
    }


def seed_if_empty(db: Session) -> None:
    if db.query(Message).count() == 0:
        seed_database(db, wipe=False)
