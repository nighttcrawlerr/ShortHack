"""Модели запросов и ответов. Имена полей совпадают с docs/01_CONTRACT.md."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel: str
    subject: str | None = None
    author_name: str
    author_email: str
    received_at: str
    body: str
    status: str


class MessageListItem(BaseModel):
    id: int
    channel: str
    subject: str | None = None
    author_name: str
    author_email: str
    received_at: str
    preview: str
    status: str
    has_analysis: bool
    category: str | None = None
    priority: str | None = None
    suggested_action: str | None = None


class MissingField(BaseModel):
    field: str
    why: str
    question: str


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: int
    summary: str
    intents: list[str] = Field(default_factory=list)
    category: str
    service: str
    priority: str
    priority_reason: str
    team: str
    entities: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[MissingField] = Field(default_factory=list)
    sentiment: str
    confidence: float
    suggested_action: str | None = None
    action_reason: str = ""
    similar_ticket_ids: list[int] = Field(default_factory=list)
    kb_article_ids: list[int] = Field(default_factory=list)
    mass_incident: bool = False
    model: str
    latency_ms: int
    created_at: str


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    message_id: int | None = None
    title: str
    description: str
    category: str
    service: str
    priority: str
    team: str
    status: str
    requester_name: str
    requester_email: str
    entities: dict[str, Any] = Field(default_factory=dict)
    resolution: str | None = None
    created_by: str
    created_at: str
    updated_at: str


class AgentStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_no: int
    kind: str
    name: str
    input_preview: str
    output_preview: str
    latency_ms: int


class OutboxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: int
    ticket_id: int | None = None
    kind: str
    subject: str
    body: str
    questions: list[str] = Field(default_factory=list)
    status: str
    created_at: str


class MessageDetailOut(BaseModel):
    message: MessageOut
    analysis: AnalysisOut | None = None
    steps: list[AgentStepOut] = Field(default_factory=list)
    tickets: list[TicketOut] = Field(default_factory=list)
    outbox: list[OutboxOut] = Field(default_factory=list)


class AnalyzeResponse(MessageDetailOut):
    pass


class CreateMessageRequest(BaseModel):
    channel: Literal["email", "call"] = "email"
    subject: str | None = None
    author_name: str = "Неизвестный отправитель"
    author_email: str = "unknown@example.ru"
    body: str
    received_at: str | None = None


class ApplyRequest(BaseModel):
    decision: Literal["confirm", "edit", "reject"]
    ticket_id: int | None = None
    outbox_id: int | None = None
    overrides: dict[str, Any] | None = None
    edited_body: str | None = None
    edited_subject: str | None = None


class TicketPatchRequest(BaseModel):
    status: str | None = None
    priority: str | None = None
    category: str | None = None
    team: str | None = None
    title: str | None = None
    description: str | None = None
    resolution: str | None = None


class SimilarTicketOut(BaseModel):
    id: int
    key: str
    title: str
    status: str
    resolution: str | None = None
    score: float


class KBHitOut(BaseModel):
    id: int
    title: str
    category: str
    excerpt: str
    score: float


class HealthOut(BaseModel):
    status: str
    llm: str
    model: str
    db_messages: int


class CountItem(BaseModel):
    code: str
    label: str
    count: int


class MassIncidentOut(BaseModel):
    category: str
    service: str
    count: int
    message_ids: list[int]
    hint: str


class StatsOut(BaseModel):
    messages_total: int
    messages_analyzed: int
    tickets_total: int
    auto_actionable_share: float
    avg_latency_ms: int
    by_category: list[CountItem]
    by_priority: list[CountItem]
    by_action: list[CountItem]
    mass_incidents: list[MassIncidentOut]
