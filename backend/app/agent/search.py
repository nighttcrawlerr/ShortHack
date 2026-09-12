"""Поиск похожих заявок и статей базы знаний. Языковая модель здесь не нужна.

Это место отдельно проговаривается на защите: мера Жаккара по нормализованным
словам плюс бонусы за совпадение категории и сервиса работают за миллисекунды
и всегда одинаково.
"""
import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import KBArticle, Message, Ticket

STOP_WORDS = {
    "это", "для", "или", "что", "как", "при", "все", "нет", "был", "есть",
    "она", "они", "его", "ещё", "еще", "так", "уже", "там", "том", "тем",
    "был", "быть", "мне", "меня", "вас", "вам", "наш", "под", "над", "без",
    "the", "and", "for", "not", "with",
}

MIN_SCORE = 0.22
MIN_SHARED_WORDS = 3

# Массовый сбой возможен только там, где сервис общий для многих людей.
# Сломанный ноутбук у одного и принтер у другого — это не общий инцидент,
# поэтому оборудование и программы в этот список не входят.
SHARED_SERVICE_CATEGORIES = {"network", "vpn", "platform", "email", "access"}
CATEGORY_BONUS = 0.15
SERVICE_BONUS = 0.10
KEYWORD_BONUS = 0.20


def normalize(text: str) -> set[str]:
    if not text:
        return set()
    cleaned = re.sub(r"[^\w\s-]", " ", text.lower(), flags=re.UNICODE)
    return {
        word
        for word in cleaned.split()
        if len(word) >= 3 and word not in STOP_WORDS
    }


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def overlap(left: set[str], right: set[str]) -> float:
    """Доля совпадения относительно более короткого текста."""
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def similarity(left: set[str], right: set[str]) -> float:
    """Смешанная мера.

    Обращение пользователя обычно длиннее заявки в несколько раз, и чистая мера
    Жаккара из-за этого занижает совпадение до нуля. Поэтому основной вес отдан
    доле совпадения относительно короткого текста, а Жаккар остаётся поправкой
    против ложных срабатываний на очень коротких заявках.
    """
    shared = left & right
    if len(shared) < MIN_SHARED_WORDS:
        return 0.0
    return round(0.65 * overlap(left, right) + 0.35 * jaccard(left, right), 4)


def search_similar_tickets(
    db: Session,
    query_text: str,
    category: str | None = None,
    service: str | None = None,
    limit: int = 5,
    exclude_message_id: int | None = None,
) -> list[dict]:
    query_words = normalize(query_text)
    results = []

    rows = db.query(Ticket).filter(Ticket.status != "rejected").all()
    for ticket in rows:
        if exclude_message_id and ticket.message_id == exclude_message_id:
            continue
        ticket_words = normalize(f"{ticket.title} {ticket.description}")
        score = similarity(query_words, ticket_words)
        if category and ticket.category == category:
            score += CATEGORY_BONUS
        if service and ticket.service and _same_service(ticket.service, service):
            score += SERVICE_BONUS
        if score >= MIN_SCORE:
            results.append(
                {
                    "id": ticket.id,
                    "key": ticket.key,
                    "title": ticket.title,
                    "status": ticket.status,
                    "resolution": ticket.resolution,
                    "score": round(min(score, 1.0), 2),
                }
            )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]


def _same_service(left: str, right: str) -> bool:
    return normalize(left) & normalize(right) != set()


def search_kb(
    db: Session,
    query_text: str,
    category: str | None = None,
    limit: int = 3,
) -> list[dict]:
    query_words = normalize(query_text)
    results = []

    for article in db.query(KBArticle).all():
        article_words = normalize(f"{article.title} {article.body}")
        score = similarity(query_words, article_words)
        for keyword in article.keywords or []:
            if keyword.lower() in query_text.lower():
                score += KEYWORD_BONUS
        if category and article.category == category:
            score += CATEGORY_BONUS
        if score >= MIN_SCORE:
            results.append(
                {
                    "id": article.id,
                    "title": article.title,
                    "category": article.category,
                    "excerpt": _excerpt(article.body),
                    "score": round(min(score, 1.0), 2),
                }
            )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]


def _excerpt(body: str, limit: int = 200) -> str:
    text = " ".join((body or "").split())
    return text[:limit] + ("…" if len(text) > limit else "")


def detect_mass_incident(
    db: Session,
    category: str,
    service: str,
    hours: int = 6,
    threshold: int = 3,
    exclude_message_id: int | None = None,
) -> tuple[bool, list[int]]:
    """Три и более обращения той же категории по тому же сервису за окно времени."""
    if category not in SHARED_SERVICE_CATEGORIES:
        return False, []

    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    ids = []

    for message in db.query(Message).filter(Message.received_at >= since).all():
        analysis = message.latest_analysis
        if analysis is None:
            continue
        if analysis.category != category:
            continue
        if service and analysis.service and not _same_service(analysis.service, service):
            continue
        ids.append(message.id)

    if exclude_message_id and exclude_message_id not in ids:
        ids.append(exclude_message_id)

    return len(ids) >= threshold, sorted(ids)
