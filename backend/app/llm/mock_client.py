"""Заглушка модели. Форма ответа совпадает с живым провайдером."""
import re
import time

from app.llm import mock_data


def _extract_entities(body: str) -> dict:
    found = {}
    for name, pattern in mock_data.ENTITY_PATTERNS.items():
        match = re.search(pattern, body, flags=re.IGNORECASE)
        if match:
            found[name] = (match.group(1) if match.groups() else match.group(0)).strip()
    return found


def _first_sentence(body: str, limit: int = 180) -> str:
    text = " ".join(body.split())
    parts = re.split(r"(?<=[.!?])\s", text)
    for part in parts:
        if len(part) > 25:
            return part[:limit]
    return text[:limit]


def extract(body: str, author_name: str = "") -> dict:
    rule = mock_data.match_rule(body)
    entities = _extract_entities(body)
    has_login = "login" in entities
    missing = []
    if not has_login:
        missing.append(
            {
                "field": "login",
                "why": "Без логина нельзя найти учётную запись и проверить настройки",
                "question": "Подскажите, пожалуйста, ваш корпоративный логин.",
            }
        )
    if rule["category"] == "other":
        missing.append(
            {
                "field": "problem_description",
                "why": "Из обращения непонятно, какой именно сервис не работает",
                "question": "Уточните, пожалуйста, что именно перестало работать и когда это началось.",
            }
        )

    who = author_name or "Пользователь"
    return {
        "summary": f"{who}: {_first_sentence(body)}",
        "intents": [_first_sentence(body, 90)],
        "category": rule["category"],
        "service": rule["service"],
        "priority": rule["priority"],
        "priority_reason": "Оценка демонстрационного режима по ключевым словам обращения",
        "team": rule["team"],
        "entities": entities,
        "missing_fields": missing,
        "sentiment": "annoyed" if any(w in body.lower() for w in ("срочно", "совсем", "уже")) else "calm",
        "confidence": 0.5,
    }


def decide(analysis: dict, similar: list, kb: list, mass_incident: bool) -> dict:
    rule = mock_data.match_rule(
        " ".join([analysis.get("summary", ""), analysis.get("service", "")])
    )
    action = rule["action"]
    if analysis.get("missing_fields"):
        action = "ask_clarification"

    service = analysis.get("service", "сервис")
    summary = analysis.get("summary", "")

    if action == "create_ticket":
        prefix = "Возможен массовый сбой, есть похожие обращения.\n" if mass_incident else ""
        hint = ""
        if similar:
            hint = f"\nПохожая заявка {similar[0]['key']}: {similar[0].get('resolution') or 'решение не указано'}"
        return {
            "name": "create_ticket",
            "arguments": {
                "title": f"{service}: {analysis.get('intents', ['обращение'])[0]}"[:80],
                "description": f"{prefix}{summary}{hint}",
                "category": analysis.get("category", "other"),
                "service": service,
                "priority": analysis.get("priority", "P3"),
                "team": analysis.get("team", "l1_support"),
            },
        }

    if action == "ask_clarification":
        questions = [m["question"] for m in analysis.get("missing_fields", [])]
        if not questions:
            questions = ["Уточните, пожалуйста, что именно не работает и когда это началось."]
        numbered = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1))
        return {
            "name": "ask_clarification",
            "arguments": {
                "subject": "Уточнение по вашему обращению",
                "body": (
                    "Здравствуйте!\n\nСпасибо за обращение. Чтобы мы могли помочь быстрее, "
                    f"уточните, пожалуйста, несколько деталей:\n\n{numbered}\n\n"
                    "С уважением, служба технической поддержки"
                ),
                "questions": questions,
            },
        }

    article = kb[0] if kb else None
    body = (
        "Здравствуйте!\n\nПо вашему вопросу есть готовая инструкция.\n\n"
        + (article["excerpt"] if article else "Инструкция уточняется.")
        + "\n\nЕсли шаги не помогут, ответьте на это письмо, и мы заведём заявку.\n\n"
        "С уважением, служба технической поддержки"
    )
    return {
        "name": "draft_reply",
        "arguments": {
            "subject": "Ответ по вашему обращению",
            "body": body,
            "kb_used": [article["id"]] if article else [],
        },
    }


def sleep_a_little() -> int:
    """Небольшая задержка, чтобы интерфейс успел показать состояние загрузки."""
    started = time.perf_counter()
    time.sleep(0.35)
    return int((time.perf_counter() - started) * 1000)
