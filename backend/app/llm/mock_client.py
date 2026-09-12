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


def _meaningful_text(body: str) -> str:
    """Из расшифровки звонка берём слова абонента, а не служебную шапку и не оператора."""
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    caller = [
        line.split(":", 1)[1].strip()
        for line in lines
        if line.lower().startswith("абонент:") and ":" in line
    ]
    if caller:
        return " ".join(caller)
    useful = [
        line
        for line in lines
        if not line.lower().startswith(("расшифровка", "оператор:", "здравствуйте", "добрый день"))
    ]
    return " ".join(useful) or " ".join(lines)


def _first_sentence(body: str, limit: int = 180) -> str:
    text = " ".join(_meaningful_text(body).split())
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
    if mass_incident:
        # То же правило, что и в системном промпте: при массовом сбое заявка нужна
        # в любом случае, даже если данных о конкретном пользователе не хватает.
        action = "create_ticket"

    service = analysis.get("service", "сервис")
    summary = analysis.get("summary", "")

    if action == "create_ticket":
        prefix = "Возможен массовый сбой, есть похожие обращения.\n" if mass_incident else ""
        hint = ""
        solved = next((item for item in similar if item.get("resolution")), None)
        if solved:
            hint = f"\nПохожая заявка {solved['key']}: {solved['resolution']}"
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


def compose(analysis: dict, passages: list, body: str, repair: bool = False) -> dict:
    """Заглушка автора ответа: собирает ответ из первого фрагмента со ссылкой.

    Намеренно не пытается быть умной. Её задача — дать проверяющему настоящий
    вход той же формы, что и живая модель, чтобы весь конвейер можно было
    отлаживать и показывать без ключа.
    """
    if not passages:
        return {
            "answer": "",
            "used_sources": [],
            "insufficient": True,
            "confidence": 0.0,
            "missing_info": "В базе знаний нет подходящей статьи",
        }

    top = passages[0]
    lines = [line.strip() for line in (top.get("text") or "").splitlines() if line.strip()]
    steps = [line for line in lines if re.match(r"^\d+[.)]\s", line)][:5]

    if steps:
        instruction = "\n".join(f"{step} [1]" for step in steps)
    else:
        sentence = next((line for line in lines[1:] if len(line) > 30), lines[-1] if lines else "")
        instruction = f"{sentence} [1]"

    answer = (
        "Здравствуйте!\n\n"
        "По вашему обращению есть готовая инструкция.\n\n"
        f"{instruction}\n\n"
        "Если шаги не помогут, ответьте на это письмо, и мы заведём заявку.\n\n"
        "С уважением, служба технической поддержки"
    )
    return {
        "answer": answer,
        "used_sources": [1],
        "insufficient": False,
        "confidence": 0.5,
        "missing_info": "",
    }


def verify(answer: str, passages: list) -> dict:
    """Заглушка проверяющего: сверяет утверждения по совпадению слов.

    Это не имитация вердикта, а честная грубая проверка: утверждение считается
    подтверждённым, если больше половины его значимых слов встречаются
    в том фрагменте, на который оно ссылается.
    """
    from app.agent.verifier import CITATION, split_sentences
    from app.rag.tokens import tokenize

    claims = []
    for sentence in split_sentences(answer):
        numbers = [int(n) for n in CITATION.findall(sentence)]
        source = numbers[0] if numbers and 1 <= numbers[0] <= len(passages) else None
        words = set(tokenize(CITATION.sub(" ", sentence)))
        if not words:
            continue
        if source is None:
            verdict, comment = "not_found", "Утверждение не ссылается на источник"
        else:
            source_words = set(tokenize(passages[source - 1].get("text", "")))
            overlap = len(words & source_words) / len(words)
            if overlap >= 0.5:
                verdict = "supported"
                comment = f"Совпадение с фрагментом {source}: {overlap:.0%} значимых слов"
            else:
                verdict = "not_found"
                comment = f"Во фрагменте {source} нашлось только {overlap:.0%} слов утверждения"
        claims.append(
            {"text": sentence[:400], "verdict": verdict, "source": source, "comment": comment}
        )
    return {"claims": claims}
