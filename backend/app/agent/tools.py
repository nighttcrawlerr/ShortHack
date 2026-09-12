"""Исполнение инструментов, которые выбрал агент.

Инструмент — это обычная функция программы. Именно переход от анализа
к вызову такой функции и составляет агентную часть проекта.
"""
from typing import Any

from sqlalchemy.orm import Session

from app.dictionaries import (
    CATEGORY_CODES,
    PRIORITY_CODES,
    TEAM_CODES,
    safe,
)
from app.models import Analysis, Message, Outbox, Ticket, now_iso

SIGNATURE = "С уважением, служба технической поддержки"


def _text(value: Any, fallback: str = "") -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _ensure_signature(body: str) -> str:
    return body if SIGNATURE in body else f"{body.rstrip()}\n\n{SIGNATURE}"


def execute_create_ticket(
    db: Session, message: Message, analysis: Analysis, args: dict
) -> tuple[Ticket, str]:
    title = _text(args.get("title"), analysis.summary[:80] or "Обращение пользователя")
    ticket = Ticket(
        message_id=message.id,
        title=title[:300],
        description=_text(args.get("description"), analysis.summary),
        category=safe(args.get("category"), CATEGORY_CODES, analysis.category),
        service=_text(args.get("service"), analysis.service),
        priority=safe(args.get("priority"), PRIORITY_CODES, analysis.priority),
        team=safe(args.get("team"), TEAM_CODES, analysis.team),
        status="proposed",
        requester_name=message.author_name,
        requester_email=message.author_email,
        entities=analysis.entities or {},
        created_by="agent",
    )
    db.add(ticket)
    db.flush()
    ticket.key = f"SD-{1000 + ticket.id}"
    db.commit()
    db.refresh(ticket)
    return ticket, ticket.key


def execute_ask_clarification(
    db: Session, message: Message, analysis: Analysis, args: dict
) -> tuple[Outbox, str]:
    questions = args.get("questions")
    if not isinstance(questions, list) or not questions:
        questions = [m.get("question", "") for m in (analysis.missing_fields or [])]
    questions = [q for q in (str(q).strip() for q in questions) if q]
    if not questions:
        questions = ["Уточните, пожалуйста, что именно не работает и когда это началось."]

    default_body = (
        "Здравствуйте!\n\nСпасибо за обращение. Чтобы помочь быстрее, уточните, "
        "пожалуйста, несколько деталей:\n\n"
        + "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1))
    )

    letter = Outbox(
        message_id=message.id,
        kind="clarification",
        subject=_text(args.get("subject"), "Уточнение по вашему обращению")[:300],
        body=_ensure_signature(_text(args.get("body"), default_body)),
        questions=questions,
        status="draft",
    )
    db.add(letter)
    db.commit()
    db.refresh(letter)
    return letter, letter.subject


def execute_draft_reply(
    db: Session, message: Message, analysis: Analysis, args: dict
) -> tuple[Outbox, str]:
    letter = Outbox(
        message_id=message.id,
        kind="reply",
        subject=_text(args.get("subject"), "Ответ по вашему обращению")[:300],
        body=_ensure_signature(
            _text(args.get("body"), "Здравствуйте! По вашему вопросу готовим ответ.")
        ),
        questions=[],
        status="draft",
    )
    db.add(letter)
    db.commit()
    db.refresh(letter)

    used = args.get("kb_used")
    if isinstance(used, list):
        analysis.kb_article_ids = [int(i) for i in used if str(i).isdigit()] or (
            analysis.kb_article_ids or []
        )
        db.commit()

    return letter, letter.subject


EXECUTORS = {
    "create_ticket": execute_create_ticket,
    "ask_clarification": execute_ask_clarification,
    "draft_reply": execute_draft_reply,
}


def execute_tool(
    db: Session, message: Message, analysis: Analysis, name: str, args: dict
) -> tuple[Any, str, str]:
    """Возвращает объект, короткую строку для трассы и фактическое имя инструмента."""
    executor = EXECUTORS.get(name)
    if executor is None:
        executor = EXECUTORS["ask_clarification"]
        name = "ask_clarification"
    obj, preview = executor(db, message, analysis, args or {})
    return obj, preview, name
