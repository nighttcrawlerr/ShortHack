"""Обучение на правках оператора.

Дообучить модель на диалогах операторов Сбера с клиентами нельзя: эти диалоги
закрыты и содержат персональные данные. Зато система порождает собственные
обучающие данные с первого дня: каждый раз, когда оператор меняет приоритет,
категорию или переписывает текст, он показывает, как правильно.

Эти правки используются двумя способами.

Сразу — подмешиваются в промпт как примеры. Это работает с первой же правки
и не требует обучения: модель видит, что в похожем случае человек поправил
приоритет, и в следующий раз ставит его сам.

Позже — выгружаются в набор для настоящего дообучения. Когда правок наберётся
несколько тысяч, из них получится обучающая выборка, и этот же интерфейс
отдаст её в нужном формате.
"""
import json

from sqlalchemy.orm import Session

from app.dictionaries import CATEGORIES, PRIORITIES, TEAMS, label_of
from app.models import Correction, Message, now_iso

MAX_EXAMPLES = 6
CONTEXT_CHARS = 260

FIELD_LABELS = {
    "priority": "приоритет",
    "category": "категория",
    "team": "команда",
    "body": "текст письма",
}

DICTS = {"priority": PRIORITIES, "category": CATEGORIES, "team": TEAMS}


def record(db: Session, message: Message, field: str, before: str, after: str) -> None:
    """Запоминает одну правку. Если оператор ничего не менял, записи нет."""
    before, after = (before or "").strip(), (after or "").strip()
    if not after or before == after:
        return

    analysis = message.latest_analysis
    db.add(
        Correction(
            message_id=message.id,
            field=field,
            before=before,
            after=after,
            context=_context(message, analysis),
            category=analysis.category if analysis else "other",
            created_at=now_iso(),
        )
    )


def _context(message: Message, analysis) -> str:
    base = (analysis.summary if analysis else "") or message.subject or message.body
    return " ".join(base.split())[:CONTEXT_CHARS]


def examples_for(db: Session, category: str | None = None) -> str:
    """Примеры правок для подстановки в промпт. Пустая строка, если их нет."""
    query = db.query(Correction).filter(Correction.field.in_(("priority", "category", "team")))
    rows = query.order_by(Correction.id.desc()).limit(MAX_EXAMPLES * 3).all()
    if not rows:
        return ""

    # Правки по той же категории важнее: они ближе к разбираемому обращению.
    rows.sort(key=lambda r: (r.category != category, -r.id))
    rows = rows[:MAX_EXAMPLES]

    lines = []
    for row in rows:
        dictionary = DICTS.get(row.field, [])
        before = label_of(dictionary, row.before) if dictionary else row.before
        after = label_of(dictionary, row.after) if dictionary else row.after
        lines.append(
            f"- «{row.context}»\n"
            f"  модель определила {FIELD_LABELS.get(row.field, row.field)}: {before}, "
            f"оператор исправил на: {after}"
        )

    return (
        "\n\nКак оператор поправлял разбор похожих обращений. Это решения живого "
        "человека, знающего свою инфраструктуру. Учитывай их: если обращение похоже "
        "на пример, ставь так, как поставил оператор.\n" + "\n".join(lines)
    )


def style_examples(db: Session, limit: int = 2) -> str:
    """Куски писем, переписанных оператором: по ним видно, какой тон здесь принят."""
    rows = (
        db.query(Correction)
        .filter(Correction.field == "body")
        .order_by(Correction.id.desc())
        .limit(limit)
        .all()
    )
    if not rows:
        return ""
    samples = "\n\n".join(f"«{row.after[:400]}»" for row in rows)
    return (
        "\n\nТак оператор переписывал письма этой службы. Держись этого тона "
        f"и построения фраз:\n{samples}"
    )


def dataset(db: Session) -> list[dict]:
    """Выгрузка для настоящего дообучения, по паре запрос-ответ на правку."""
    rows = db.query(Correction).order_by(Correction.id).all()
    out = []
    for row in rows:
        dictionary = DICTS.get(row.field, [])
        after = label_of(dictionary, row.after) if dictionary else row.after
        out.append(
            {
                "request": [
                    {
                        "role": "system",
                        "text": "Определи параметры обращения в техническую поддержку.",
                    },
                    {
                        "role": "user",
                        "text": f"Обращение: {row.context}\nЧто определить: "
                        f"{FIELD_LABELS.get(row.field, row.field)}",
                    },
                ],
                "response": after,
            }
        )
    return out


def dataset_jsonl(db: Session) -> str:
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in dataset(db))
