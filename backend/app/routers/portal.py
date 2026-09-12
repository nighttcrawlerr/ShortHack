"""Окно пользователя: отправить обращение и получить ответ.

Это вторая сторона продукта. Здесь нет ни разбора, ни трассы, ни оценок:
человеку, у которого не работает VPN, они не нужны и только пугают.
Он видит то же, что увидел бы в письме от поддержки.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.dictionaries import CATEGORIES, CATEGORY_CODES, label_of
from app.models import Message, Outbox, now_iso
from app.schemas import PortalAskRequest, PortalReply, PortalTurn

router = APIRouter(prefix="/api/portal", tags=["portal"])

# Приветствие показывается под заголовком «Здравствуйте! Я SaluteAgent»,
# поэтому само здоровается не второй раз, а сразу переходит к делу.
GREETING = (
    "Опишите, что случилось, своими словами. Если знаете логин, код ошибки "
    "или номер кабинета, укажите их сразу: так мы решим вопрос быстрее."
)

WAITING = (
    "Спасибо за обращение. Мы передали его специалисту, он ответит вам "
    "в ближайшее время."
)


def _outcome(db: Session, message: Message) -> PortalReply:
    """Собирает то, что видит пользователь, из результата разбора."""
    analysis = message.latest_analysis
    if analysis is None:
        return PortalReply(message_id=message.id, status="pending_human", reply=WAITING)

    letter = next((o for o in message.outbox if o.status == "sent"), None)
    ticket = next(
        (t for t in message.tickets if t.status in ("open", "waiting_user")), None
    )

    if not analysis.auto_sent:
        return PortalReply(
            message_id=message.id,
            status="pending_human",
            reply=WAITING,
            elapsed_ms=analysis.latency_ms,
        )

    sources = [
        {"title": p.get("title", ""), "source": p.get("source", "")}
        for p in (analysis.passages or [])
        if p.get("chunk_id") in _cited(analysis)
    ]

    if letter is not None and letter.kind == "reply":
        return PortalReply(
            message_id=message.id,
            status="answered",
            reply=letter.body,
            sources=sources,
            elapsed_ms=analysis.latency_ms,
        )

    if letter is not None and letter.kind == "clarification":
        return PortalReply(
            message_id=message.id,
            status="clarification",
            reply=letter.body,
            questions=letter.questions or [],
            elapsed_ms=analysis.latency_ms,
        )

    if ticket is not None:
        body = (
            f"Мы приняли обращение и завели заявку {ticket.key}.\n\n"
            f"{ticket.title}\n\n"
            "Специалист свяжется с вами. Номер заявки пригодится, "
            "если захотите уточнить статус."
        )
        _remember(db, message, ticket.id, "ticket_ack",
                  f"Заявка {ticket.key} принята", body)
        return PortalReply(
            message_id=message.id,
            status="ticket_created",
            ticket_key=ticket.key,
            reply=body,
            elapsed_ms=analysis.latency_ms,
        )

    return PortalReply(
        message_id=message.id, status="pending_human", reply=WAITING,
        elapsed_ms=analysis.latency_ms,
    )


def _remember(db: Session, message: Message, ticket_id: int | None,
              kind: str, subject: str, body: str) -> None:
    """Кладёт письмо в переписку, если такого там ещё нет.

    Подтверждение о заведении заявки раньше только возвращалось в ответе
    и нигде не сохранялось: стоило пользователю обновить страницу, и от всей
    переписки оставалось его собственное сообщение. Проверять на искажения
    здесь нечего — текст шаблонный, модель его не писала.
    """
    exists = any(o.kind == kind and o.ticket_id == ticket_id for o in message.outbox)
    if exists:
        return
    db.add(Outbox(
        message_id=message.id, ticket_id=ticket_id, kind=kind,
        subject=subject[:300], body=body, status="sent",
    ))
    db.commit()
    db.refresh(message)


def _cited(analysis) -> set[int]:
    """Фрагменты, на которые ответ действительно сослался."""
    verification = analysis.verification or {}
    used = {
        claim.get("source")
        for claim in verification.get("claims", [])
        if claim.get("source")
    }
    passages = analysis.passages or []
    return {
        passages[number - 1]["chunk_id"]
        for number in used
        if isinstance(number, int) and 1 <= number <= len(passages)
    }


GREETINGS = re.compile(
    r"^\s*(здравствуйте|добрый день|добрый вечер|доброе утро|привет|здрасте)"
    r"[!,.\s]*",
    re.I,
)


def _subject(text: str, category: str | None) -> str:
    """Тема для инбокса оператора.

    Первая строка обращения почти всегда начинается с приветствия и обрывается
    на полуслове, если резать по числу символов. Приветствие убираем, режем
    по границе слова.
    """
    first = ""
    for line in text.splitlines():
        cleaned = GREETINGS.sub("", line).strip()
        if len(cleaned) > 12:
            first = cleaned
            break
    if not first:
        first = GREETINGS.sub("", text).strip() or text.strip()

    limit = 58 if category else 78
    if len(first) > limit:
        cut = first[:limit]
        space = cut.rfind(" ")
        first = (cut[:space] if space > limit // 2 else cut).rstrip(" ,;:-") + "…"

    return f"{label_of(CATEGORIES, category)}: {first}" if category else first


@router.get("/categories")
def categories() -> dict:
    return {"categories": CATEGORIES, "greeting": GREETING}


@router.post("/ask", response_model=PortalReply)
def ask(payload: PortalAskRequest, db: Session = Depends(get_db)) -> PortalReply:
    from app.agent.runner import run_analysis

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Напишите, что случилось")

    if payload.message_id:
        # Продолжение разговора: ответ пользователя дописывается к обращению,
        # и оно разбирается заново уже с новыми данными.
        message = db.get(Message, payload.message_id)
        if message is None:
            raise HTTPException(status_code=404, detail="Обращение не найдено")
        message.body = f"{message.body}\n\nДополнение от пользователя:\n{text}"
        message.status = "new"
        db.commit()
        run_analysis(db, message, force=True)
        return _outcome(db, message)

    category = payload.category if payload.category in CATEGORY_CODES else None
    subject = _subject(text, category)

    message = Message(
        channel="email",
        subject=subject,
        author_name=payload.author_name or "Пользователь портала",
        author_email=payload.author_email or "user@example.ru",
        received_at=now_iso(),
        body=text,
        status="new",
        client_category=category,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    run_analysis(db, message)
    return _outcome(db, message)


@router.get("/thread/{message_id}", response_model=list[PortalTurn])
def thread(message_id: int, db: Session = Depends(get_db)) -> list[PortalTurn]:
    message = db.get(Message, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Обращение не найдено")

    turns = [PortalTurn(role="user", text=message.body, at=message.received_at)]
    for letter in message.outbox:
        if letter.status == "sent":
            turns.append(
                PortalTurn(role="assistant", text=letter.body, at=letter.created_at)
            )
    return turns
