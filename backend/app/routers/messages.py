"""Обращения: список, карточка, ручное создание, разбор, применение решения."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Message, now_iso
from app.schemas import CreateMessageRequest, MessageListItem, MessageDetailOut, MessageOut
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
