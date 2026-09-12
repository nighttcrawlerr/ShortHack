"""Обращения: список, карточка, ручное создание, разбор, применение решения."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.dictionaries import CATEGORY_CODES, PRIORITY_CODES, TEAM_CODES, safe
from app.models import Message, now_iso
from app.schemas import (
    ApplyRequest,
    CreateMessageRequest,
    MessageDetailOut,
    MessageListItem,
    MessageOut,
)
from app.serializers import build_detail, list_item

router = APIRouter(prefix="/api/messages", tags=["messages"])


def _get_or_404(db: Session, message_id: int) -> Message:
    message = db.get(Message, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Обращение не найдено")
    return message


@router.get("", response_model=list[MessageListItem])
def list_messages(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[MessageListItem]:
    query = db.query(Message)
    if status:
        query = query.filter(Message.status == status)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Message.subject.ilike(pattern),
                Message.body.ilike(pattern),
                Message.author_name.ilike(pattern),
            )
        )
    rows = query.order_by(Message.received_at.desc()).limit(limit).all()
    return [list_item(m) for m in rows]


@router.post("/analyze-all", response_model=dict)
def analyze_all(
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """Разобрать всю неразобранную очередь.

    Нужно, чтобы жюри и менторы открывали приложение на заполненных данных,
    а не на пустом дашборде.
    """
    from app.agent.runner import run_analysis

    pending = (
        db.query(Message)
        .filter(Message.status == "new")
        .order_by(Message.received_at.asc())
        .limit(limit)
        .all()
    )

    done, failed = 0, 0
    for message in pending:
        try:
            run_analysis(db, message)
            done += 1
        except Exception:  # noqa: BLE001  одно плохое обращение не должно ломать пакет
            failed += 1
    return {"analyzed": done, "failed": failed, "pending_before": len(pending)}


@router.get("/{message_id}", response_model=MessageDetailOut)
def get_message(message_id: int, db: Session = Depends(get_db)) -> MessageDetailOut:
    return build_detail(db, _get_or_404(db, message_id))


@router.post("", response_model=MessageOut, status_code=201)
def create_message(
    payload: CreateMessageRequest, db: Session = Depends(get_db)
) -> MessageOut:
    if not payload.body.strip():
        raise HTTPException(status_code=400, detail="Текст обращения не может быть пустым")

    message = Message(
        channel=payload.channel,
        subject=payload.subject,
        author_name=payload.author_name or "Неизвестный отправитель",
        author_email=payload.author_email or "unknown@example.ru",
        received_at=payload.received_at or now_iso(),
        body=payload.body,
        status="new",
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return MessageOut.model_validate(message)


@router.post("/{message_id}/analyze", response_model=MessageDetailOut)
def analyze_message(
    message_id: int,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> MessageDetailOut:
    from app.agent.runner import run_analysis

    message = _get_or_404(db, message_id)
    try:
        run_analysis(db, message, force=force)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Разбор не удался: {exc}") from exc
    return build_detail(db, message)


@router.post("/{message_id}/apply", response_model=MessageDetailOut)
def apply_decision(
    message_id: int, payload: ApplyRequest, db: Session = Depends(get_db)
) -> MessageDetailOut:
    message = _get_or_404(db, message_id)
    analysis = message.latest_analysis
    if analysis is None:
        raise HTTPException(status_code=400, detail="Обращение ещё не разобрано")

    tickets = [t for t in message.tickets if t.status == "proposed"]
    if payload.ticket_id:
        tickets = [t for t in message.tickets if t.id == payload.ticket_id]
    letters = [o for o in message.outbox if o.status == "draft"]
    if payload.outbox_id:
        letters = [o for o in message.outbox if o.id == payload.outbox_id]

    if payload.decision == "reject":
        for ticket in tickets:
            ticket.status = "rejected"
            ticket.updated_at = now_iso()
        message.status = "new"
        db.commit()
        return build_detail(db, message)

    if payload.decision == "edit":
        overrides = payload.overrides or {}
        for ticket in tickets:
            if "category" in overrides:
                ticket.category = safe(overrides["category"], CATEGORY_CODES, ticket.category)
            if "priority" in overrides:
                ticket.priority = safe(overrides["priority"], PRIORITY_CODES, ticket.priority)
            if "team" in overrides:
                ticket.team = safe(overrides["team"], TEAM_CODES, ticket.team)
            if isinstance(overrides.get("title"), str) and overrides["title"].strip():
                ticket.title = overrides["title"].strip()[:300]
            if isinstance(overrides.get("description"), str):
                ticket.description = overrides["description"]
            if isinstance(overrides.get("service"), str) and overrides["service"].strip():
                ticket.service = overrides["service"].strip()
            ticket.updated_at = now_iso()
        for letter in letters:
            if payload.edited_body:
                letter.body = payload.edited_body
            if payload.edited_subject:
                letter.subject = payload.edited_subject[:300]

    for ticket in tickets:
        ticket.status = "open"
        ticket.updated_at = now_iso()
    for letter in letters:
        letter.status = "sent"
        if letter.kind == "clarification":
            for ticket in tickets:
                ticket.status = "waiting_user"

    message.status = "processed"
    db.commit()
    return build_detail(db, message)
