"""Агрегаты для дашборда."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.dictionaries import ACTIONS, CATEGORIES, PRIORITIES, label_of
from app.agent.search import SHARED_SERVICE_CATEGORIES
from app.models import Analysis, Message, Ticket
from app.schemas import CountItem, MassIncidentOut, StatsOut

CONFIDENT = 0.7
MASS_WINDOW_HOURS = 6
MASS_THRESHOLD = 3


def _counts(values: list[str], dictionary: list[dict]) -> list[CountItem]:
    counter = Counter(values)
    items = [
        CountItem(code=code, label=label_of(dictionary, code), count=count)
        for code, count in counter.items()
    ]
    items.sort(key=lambda item: item.count, reverse=True)
    return items


def _plural_hours(hours: int) -> str:
    if hours == 1:
        return "час"
    if 2 <= hours <= 4:
        return "часа"
    return "часов"


def _plural_messages(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "обращение"
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return "обращения"
    return "обращений"


def build_stats(db: Session) -> StatsOut:
    messages = db.query(Message).all()
    analyses = db.query(Analysis).all()
    tickets = db.query(Ticket).all()

    latest: dict[int, Analysis] = {}
    for analysis in analyses:
        latest[analysis.message_id] = analysis
    current = list(latest.values())

    confident = [a for a in current if (a.confidence or 0) >= CONFIDENT]
    share = round(len(confident) / len(current), 2) if current else 0.0
    avg_latency = int(sum(a.latency_ms or 0 for a in current) / len(current)) if current else 0

    since = (datetime.now() - timedelta(hours=MASS_WINDOW_HOURS)).isoformat()
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for message in messages:
        analysis = latest.get(message.id)
        if analysis is None or message.received_at < since:
            continue
        if analysis.category not in SHARED_SERVICE_CATEGORIES:
            continue
        groups[(analysis.category, analysis.service or "")].append(message.id)

    incidents = []
    for (category, service), ids in groups.items():
        if len(ids) < MASS_THRESHOLD:
            continue
        label = label_of(CATEGORIES, category)
        incidents.append(
            MassIncidentOut(
                category=category,
                service=service,
                count=len(ids),
                message_ids=sorted(ids),
                hint=(
                    f"{len(ids)} {_plural_messages(len(ids))} по направлению «{service or label}» "
                    f"за последние {MASS_WINDOW_HOURS} {_plural_hours(MASS_WINDOW_HOURS)}, "
                    "возможен массовый сбой"
                ),
            )
        )
    incidents.sort(key=lambda item: item.count, reverse=True)

    return StatsOut(
        messages_total=len(messages),
        messages_analyzed=len(current),
        tickets_total=len([t for t in tickets if t.created_by == "agent"]),
        auto_actionable_share=share,
        avg_latency_ms=avg_latency,
        by_category=_counts([a.category for a in current], CATEGORIES),
        by_priority=_counts([a.priority for a in current], PRIORITIES),
        by_action=_counts(
            [a.suggested_action for a in current if a.suggested_action], ACTIONS
        ),
        mass_incidents=incidents,
    )
