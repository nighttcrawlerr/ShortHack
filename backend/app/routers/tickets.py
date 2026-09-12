"""Заявки: список с фильтрами и правка полей оператором."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.dictionaries import (
    CATEGORY_CODES,
    PRIORITY_CODES,
    TEAM_CODES,
    TICKET_STATUS_CODES,
    safe,
)
from app.agent.tools import SIGNATURE
from app.models import Outbox, Ticket, now_iso
from app.schemas import TicketOut, TicketPatchRequest

router = APIRouter(prefix="/api/tickets", tags=["tickets"])

PRIORITY_ORDER = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}


@router.get("", response_model=list[TicketOut])
def list_tickets(
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[TicketOut]:
    query = db.query(Ticket)
    if status:
        query = query.filter(Ticket.status == status)
    if category:
        query = query.filter(Ticket.category == category)
    if priority:
        query = query.filter(Ticket.priority == priority)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Ticket.title.ilike(pattern),
                Ticket.description.ilike(pattern),
                Ticket.key.ilike(pattern),
                Ticket.requester_name.ilike(pattern),
            )
        )
    rows = query.all()
    rows.sort(key=lambda t: (PRIORITY_ORDER.get(t.priority, 9), -t.id))
    return [TicketOut.model_validate(t) for t in rows]


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)) -> TicketOut:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return TicketOut.model_validate(ticket)


@router.patch("/{ticket_id}", response_model=TicketOut)
def patch_ticket(
    ticket_id: int, payload: TicketPatchRequest, db: Session = Depends(get_db)
) -> TicketOut:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    was = ticket.status
    if payload.status is not None:
        ticket.status = safe(payload.status, TICKET_STATUS_CODES, ticket.status)
    if payload.priority is not None:
        ticket.priority = safe(payload.priority, PRIORITY_CODES, ticket.priority)
    if payload.category is not None:
        ticket.category = safe(payload.category, CATEGORY_CODES, ticket.category)
    if payload.team is not None:
        ticket.team = safe(payload.team, TEAM_CODES, ticket.team)
    if payload.title is not None and payload.title.strip():
        ticket.title = payload.title.strip()[:300]
    if payload.description is not None:
        ticket.description = payload.description
    if payload.resolution is not None:
        ticket.resolution = payload.resolution

    ticket.updated_at = now_iso()
    db.commit()

    _notify_requester(db, ticket, was)

    db.refresh(ticket)
    return TicketOut.model_validate(ticket)


CLOSING = {"closed", "rejected"}


def _notify_requester(db: Session, ticket: Ticket, was: str) -> None:
    """Пишет пользователю, когда оператор закрывает его заявку.

    До этого заявка закрывалась молча: человек оставлял обращение, получал
    номер и больше не слышал ничего — ни что работы закончены, ни что
    именно сделали. Письмо появляется в его переписке на портале.
    """
    if ticket.status not in CLOSING or was in CLOSING or ticket.message_id is None:
        return

    resolution = (ticket.resolution or "").strip()

    if ticket.status == "closed":
        head = f"По вашей заявке {ticket.key} работы завершены."
        tail = "Если проблема повторится, напишите нам ещё раз."
    else:
        head = f"Заявка {ticket.key} закрыта без выполнения."
        tail = "Если мы поняли вопрос неверно, напишите нам ещё раз."

    parts = ["Здравствуйте!", head]
    if resolution:
        parts.append(resolution)
    parts.extend([tail, SIGNATURE])

    db.add(Outbox(
        message_id=ticket.message_id,
        ticket_id=ticket.id,
        kind="resolution",
        subject=f"Заявка {ticket.key} закрыта"[:300],
        body="\n\n".join(parts),
        status="sent",
    ))
    db.commit()
