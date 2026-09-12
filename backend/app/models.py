"""Модели таблиц. Поля-объекты хранятся в SQLite текстом и разбираются прозрачно."""
import json
from datetime import datetime, timezone

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class JSONText(TypeDecorator):
    """Хранит списки и словари текстом, наружу отдаёт готовый объект."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if value is None or value == "":
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[str] = mapped_column(String(16), default="email")
    subject: Mapped[str | None] = mapped_column(String(300), nullable=True)
    author_name: Mapped[str] = mapped_column(String(200), default="")
    author_email: Mapped[str] = mapped_column(String(200), default="")
    received_at: Mapped[str] = mapped_column(String(40), default=now_iso)
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="new")
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)

    analyses: Mapped[list["Analysis"]] = relationship(
        back_populates="message", cascade="all, delete-orphan", order_by="Analysis.id"
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="message", order_by="Ticket.id"
    )
    steps: Mapped[list["AgentStep"]] = relationship(
        back_populates="message", cascade="all, delete-orphan", order_by="AgentStep.step_no"
    )
    outbox: Mapped[list["Outbox"]] = relationship(
        back_populates="message", cascade="all, delete-orphan", order_by="Outbox.id"
    )

    @property
    def latest_analysis(self) -> "Analysis | None":
        return self.analyses[-1] if self.analyses else None


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))

    summary: Mapped[str] = mapped_column(Text, default="")
    intents: Mapped[list] = mapped_column(JSONText, default=list)
    category: Mapped[str] = mapped_column(String(32), default="other")
    service: Mapped[str] = mapped_column(String(200), default="")
    priority: Mapped[str] = mapped_column(String(8), default="P3")
    priority_reason: Mapped[str] = mapped_column(Text, default="")
    team: Mapped[str] = mapped_column(String(32), default="l1_support")
    entities: Mapped[dict] = mapped_column(JSONText, default=dict)
    missing_fields: Mapped[list] = mapped_column(JSONText, default=list)
    sentiment: Mapped[str] = mapped_column(String(16), default="calm")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)

    suggested_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action_reason: Mapped[str] = mapped_column(Text, default="")
    similar_ticket_ids: Mapped[list] = mapped_column(JSONText, default=list)
    kb_article_ids: Mapped[list] = mapped_column(JSONText, default=list)
    mass_incident: Mapped[bool] = mapped_column(Boolean, default=False)

    model: Mapped[str] = mapped_column(String(80), default="mock")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    raw_llm: Mapped[dict | None] = mapped_column(JSONText, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)

    message: Mapped["Message"] = relationship(back_populates="analyses")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(20), default="")
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32), default="other")
    service: Mapped[str] = mapped_column(String(200), default="")
    priority: Mapped[str] = mapped_column(String(8), default="P3")
    team: Mapped[str] = mapped_column(String(32), default="l1_support")
    status: Mapped[str] = mapped_column(String(20), default="proposed")

    requester_name: Mapped[str] = mapped_column(String(200), default="")
    requester_email: Mapped[str] = mapped_column(String(200), default="")
    entities: Mapped[dict] = mapped_column(JSONText, default=dict)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[str] = mapped_column(String(16), default="agent")
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)
    updated_at: Mapped[str] = mapped_column(String(40), default=now_iso)

    message: Mapped["Message | None"] = relationship(back_populates="tickets")


class KBArticle(Base):
    __tablename__ = "kb_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    category: Mapped[str] = mapped_column(String(32), default="other")
    service: Mapped[str] = mapped_column(String(200), default="")
    keywords: Mapped[list] = mapped_column(JSONText, default=list)
    body: Mapped[str] = mapped_column(Text, default="")


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    step_no: Mapped[int] = mapped_column(Integer, default=1)
    kind: Mapped[str] = mapped_column(String(8), default="tool")
    name: Mapped[str] = mapped_column(String(64), default="")
    input_preview: Mapped[str] = mapped_column(Text, default="")
    output_preview: Mapped[str] = mapped_column(Text, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)

    message: Mapped["Message"] = relationship(back_populates="steps")


class Outbox(Base):
    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    ticket_id: Mapped[int | None] = mapped_column(
        ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(20), default="clarification")
    subject: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    questions: Mapped[list] = mapped_column(JSONText, default=list)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)

    message: Mapped["Message"] = relationship(back_populates="outbox")
