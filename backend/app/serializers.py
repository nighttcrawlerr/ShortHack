"""Сборка ответов API из моделей."""
from sqlalchemy.orm import Session

from app.models import Message
from app.schemas import (
    AgentStepOut,
    AnalysisOut,
    MessageDetailOut,
    MessageListItem,
    MessageOut,
    OutboxOut,
    TicketOut,
)

PREVIEW_LEN = 160


def make_preview(body: str) -> str:
    text = " ".join((body or "").split())
    if len(text) <= PREVIEW_LEN:
        return text
    return text[:PREVIEW_LEN].rstrip() + "…"


def list_item(message: Message) -> MessageListItem:
    analysis = message.latest_analysis
    return MessageListItem(
        id=message.id,
        channel=message.channel,
        subject=message.subject,
        author_name=message.author_name,
        author_email=message.author_email,
        received_at=message.received_at,
        preview=make_preview(message.body),
        status=message.status,
        has_analysis=analysis is not None,
        category=analysis.category if analysis else None,
        priority=analysis.priority if analysis else None,
        suggested_action=analysis.suggested_action if analysis else None,
        auto_sent=bool(analysis and analysis.auto_sent),
        needs_human=bool(analysis and not analysis.auto_sent and message.status == "analyzed"),
    )


def build_detail(db: Session, message: Message) -> MessageDetailOut:
    db.refresh(message)
    analysis = message.latest_analysis
    return MessageDetailOut(
        message=MessageOut.model_validate(message),
        analysis=AnalysisOut.model_validate(analysis) if analysis else None,
        steps=[AgentStepOut.model_validate(s) for s in message.steps],
        tickets=[TicketOut.model_validate(t) for t in message.tickets],
        outbox=[OutboxOut.model_validate(o) for o in message.outbox],
    )
