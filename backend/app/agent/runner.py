"""Оркестратор агента. Пять шагов: разбор, два поиска, выбор действия, исполнение."""
import json
import time
from typing import Any

from sqlalchemy.orm import Session

from app.agent import roles, search, tools
from app.config import settings
from app.dictionaries import (
    ACTION_CODES,
    CATEGORIES,
    CATEGORY_CODES,
    PRIORITY_CODES,
    SENTIMENT_CODES,
    TEAM_CODES,
    label_of,
    CHANNELS,
    safe,
)
from app.llm import prompts
from app.llm.client import get_llm_client
from app.models import AgentStep, Analysis, Message
from app.rag.retriever import Retriever

PREVIEW = 500

ENTITY_KEYS = {
    "login", "full_name", "email", "phone", "employee_id", "service_name",
    "device", "os", "browser", "error_code", "occurred_at", "location",
    "inventory_number",
}


def _cut(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(text.split())
    return text[:PREVIEW] + ("…" if len(text) > PREVIEW else "")


class Trace:
    """Накопитель шагов. Пишется в базу одним куском в конце прогона."""

    def __init__(self, db: Session, message_id: int) -> None:
        self.db = db
        self.message_id = message_id
        self.steps: list[AgentStep] = []
        self.total_ms = 0

    def add(self, kind: str, name: str, inp: Any, out: Any, ms: int) -> None:
        self.total_ms += ms
        self.steps.append(
            AgentStep(
                message_id=self.message_id,
                step_no=len(self.steps) + 1,
                kind=kind,
                name=name,
                input_preview=_cut(inp),
                output_preview=_cut(out),
                latency_ms=ms,
            )
        )

    def flush(self) -> None:
        for step in self.steps:
            self.db.add(step)
        self.db.commit()


# --- шаг 1 -----------------------------------------------------------------


def _validate_extract(raw: dict) -> dict:
    """Модель могла отойти от схемы. Приводим к безопасному виду, не падая."""
    if not isinstance(raw, dict):
        raw = {}

    confidence = raw.get("confidence")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.4
    confidence = min(max(confidence, 0.0), 1.0)

    category = raw.get("category")
    priority = raw.get("priority")
    team = raw.get("team")
    if category not in CATEGORY_CODES or priority not in PRIORITY_CODES or team not in TEAM_CODES:
        confidence = min(confidence, 0.4)

    entities = raw.get("entities")
    if not isinstance(entities, dict):
        entities = {}
    entities = {
        key: str(value)
        for key, value in entities.items()
        if key in ENTITY_KEYS and value not in (None, "", [], {})
    }

    missing = []
    for item in raw.get("missing_fields") or []:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        if not question:
            continue
        missing.append(
            {
                "field": str(item.get("field", "")).strip() or "уточнение",
                "why": str(item.get("why", "")).strip(),
                "question": question,
            }
        )

    intents = [str(i).strip() for i in (raw.get("intents") or []) if str(i).strip()]

    return {
        "summary": str(raw.get("summary", "")).strip() or "Не удалось составить резюме",
        "intents": intents,
        "category": safe(category, CATEGORY_CODES, "other"),
        "service": str(raw.get("service", "")).strip() or "Не определён",
        "priority": safe(priority, PRIORITY_CODES, "P3"),
        "priority_reason": str(raw.get("priority_reason", "")).strip(),
        "team": safe(team, TEAM_CODES, "l1_support"),
        "entities": entities,
        "missing_fields": missing,
        "sentiment": safe(raw.get("sentiment"), SENTIMENT_CODES, "calm"),
        "confidence": round(confidence, 2),
    }


def _extract(client, message: Message, trace: Trace) -> dict:
    user_prompt = prompts.USER_EXTRACT_TEMPLATE.format(
        channel_label=label_of(CHANNELS, message.channel),
        subject=message.subject or "без темы",
        author_name=message.author_name,
        author_email=message.author_email,
        received_at=message.received_at,
        client_hint=(
            f"Пользователь отнёс обращение к категории: "
            f"{label_of(CATEGORIES, message.client_category)}\n"
            if message.client_category
            else ""
        ),
        body=message.body,
    )
    raw, ms = client.complete_json(
        prompts.SYSTEM_EXTRACT,
        user_prompt,
        prompts.EXTRACT_SCHEMA,
        context={
            "kind": "extract",
            "body": message.body,
            "author_name": message.author_name,
        },
    )
    clean = _validate_extract(raw)
    trace.add("llm", "extract_structure", user_prompt, clean, ms)
    return clean


def _search_query(message: Message, extracted: dict) -> str:
    """Запрос к поиску собирается из разбора, а не из письма целиком.

    В письме половина текста — приветствие, извинения и описание того, как
    человек расстроен. Для поиска это шум: он размывает совпадение и тянет
    выдачу к статьям, где просто много общих слов. Модель на первом шаге уже
    выделила суть, сервис и найденные коды ошибок — из них и собираем запрос.
    """
    parts: list[str] = []

    if message.subject:
        parts.append(message.subject)

    parts.extend(extracted.get("intents") or [])
    parts.append(extracted.get("summary", ""))

    service = extracted.get("service", "")
    if service and service != "Не определён":
        parts.append(service)

    entities = extracted.get("entities") or {}
    for key in ("error_code", "service_name", "device", "os", "browser"):
        value = entities.get(key)
        if value:
            parts.append(str(value))

    return " ".join(part for part in parts if part).strip() or message.body


# --- шаг 4 -----------------------------------------------------------------


def _decide(client, extracted: dict, similar: list, kb: list, mass: bool, trace: Trace) -> dict:
    payload = {
        "разбор": {
            "summary": extracted["summary"],
            "intents": extracted["intents"],
            "category": extracted["category"],
            "service": extracted["service"],
            "priority": extracted["priority"],
            "team": extracted["team"],
            "entities": extracted["entities"],
            "missing_fields": extracted["missing_fields"],
            "confidence": extracted["confidence"],
        },
        "похожие_заявки": [
            {
                "key": item["key"],
                "title": item["title"],
                "status": item["status"],
                "решение": item.get("resolution"),
            }
            for item in similar
        ],
        "база_знаний": [
            {"id": item["id"], "title": item["title"], "фрагмент": item["excerpt"]}
            for item in kb
        ],
        "признак_массового_сбоя": mass,
    }
    user_prompt = json.dumps(payload, ensure_ascii=False, indent=2)
    context = {
        "kind": "decide",
        "analysis": extracted,
        "similar": similar,
        "kb": kb,
        "mass_incident": mass,
    }

    if settings.llm_tools.lower() == "json":
        raw, ms = client.complete_json(
            prompts.SYSTEM_DECIDE + prompts.DECIDE_JSON_SUFFIX
            + json.dumps(prompts.TOOLS, ensure_ascii=False),
            user_prompt,
            prompts.DECIDE_JSON_SCHEMA,
            context=context,
        )
        chosen = {
            "name": raw.get("action"),
            "arguments": raw.get("arguments") if isinstance(raw.get("arguments"), dict) else {},
        }
    else:
        chosen, ms = client.complete_tools(
            prompts.SYSTEM_DECIDE, user_prompt, prompts.TOOLS, context=context
        )

    name = chosen.get("name")
    if name not in ACTION_CODES:
        name = "ask_clarification" if extracted["missing_fields"] else "create_ticket"
        chosen["name"] = name

    trace.add("llm", "decide_action", payload, name, ms)
    return chosen


# --- полный прогон ---------------------------------------------------------


def run_analysis(db: Session, message: Message, force: bool = False) -> Analysis:
    existing = message.latest_analysis
    if existing is not None and not force:
        return existing

    if force:
        # Повторный разбор должен начинаться с чистого листа: иначе рядом
        # с новым решением остаются черновики предыдущего прогона.
        for step in list(message.steps):
            db.delete(step)
        for letter in list(message.outbox):
            if letter.status == "draft":
                db.delete(letter)
        for ticket in list(message.tickets):
            if ticket.status == "proposed":
                db.delete(ticket)
        db.commit()

    client = get_llm_client()
    trace = Trace(db, message.id)
    started = time.perf_counter()

    extracted = _extract(client, message, trace)

    analysis = Analysis(message_id=message.id, **extracted)
    analysis.model = getattr(client, "model_name", "mock")
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    query_text = _search_query(message, extracted)

    t0 = time.perf_counter()
    similar = search.search_similar_tickets(
        db, query_text, extracted["category"], extracted["service"],
        exclude_message_id=message.id,
    )
    trace.add(
        "tool", "search_similar_tickets",
        f"{extracted['category']} / {extracted['service']}",
        f"найдено: {len(similar)}" + (f", лучшая {similar[0]['key']}" if similar else ""),
        int((time.perf_counter() - t0) * 1000),
    )

    t0 = time.perf_counter()
    retriever = Retriever(db)
    passages = [
        p.as_dict()
        for p in retriever.search(query_text, extracted["category"], limit=4)
    ]
    kb = [
        {
            "id": p["article_id"],
            "title": p["title"],
            "excerpt": p["text"][:200],
            "score": p["score"],
        }
        for p in passages
    ]
    trace.add(
        "tool", "search_knowledge_base",
        f"{retriever.mode()} поиск: {extracted['category']} / {extracted['service']}",
        f"фрагментов: {len(passages)}" + (f", лучший «{passages[0]['title']}»" if passages else ""),
        int((time.perf_counter() - t0) * 1000),
    )

    analysis.passages = passages
    analysis.retrieval_mode = retriever.mode()
    db.commit()

    mass, mass_ids = search.detect_mass_incident(
        db, extracted["category"], extracted["service"], exclude_message_id=message.id
    )

    try:
        chosen = _decide(client, extracted, similar, kb, mass, trace)
    except Exception as exc:  # noqa: BLE001  демонстрация не должна падать
        trace.add("tool", "error", "decide_action", f"ошибка: {exc}", 0)
        chosen = {
            "name": "ask_clarification" if extracted["missing_fields"] else "create_ticket",
            "arguments": {},
        }

    # Ответ пользователю пишет отдельная роль и только по найденным фрагментам,
    # после чего его проверяет другая роль. Если проверка не пройдена,
    # ответ не отправляется: обращение уходит человеку с заявкой.
    verdict = None
    if chosen["name"] == "draft_reply":
        if not passages:
            trace.add("tool", "verify_answer", "фрагментов не найдено",
                      "отвечать не на чем, переключаюсь на заявку", 0)
            chosen = {"name": "create_ticket", "arguments": {}}
        else:
            draft, verdict = roles.compose_and_verify(
                client, message, extracted, passages, trace
            )
            if verdict.status in ("verified", "needs_review") and not draft["insufficient"]:
                chosen["arguments"] = {
                    "subject": chosen.get("arguments", {}).get(
                        "subject", "Ответ по вашему обращению"
                    ),
                    "body": draft["answer"],
                    "kb_used": [
                        passages[n - 1]["article_id"]
                        for n in draft["used_sources"]
                        if 1 <= n <= len(passages)
                    ],
                }
            else:
                reason = (
                    "нечем ответить по базе знаний"
                    if draft["insufficient"]
                    else f"ответ отклонён проверкой ({verdict.status})"
                )
                trace.add("tool", "guard", reason,
                          "готовый ответ не отправляется, обращение уходит человеку", 0)
                chosen = {
                    "name": "ask_clarification" if extracted["missing_fields"] else "create_ticket",
                    "arguments": {},
                }

    analysis.verification = verdict.as_dict() if verdict is not None else None
    db.commit()

    t0 = time.perf_counter()
    try:
        _obj, preview, tool_name = tools.execute_tool(
            db, message, analysis, chosen["name"], chosen.get("arguments") or {}
        )
    except Exception as exc:  # noqa: BLE001
        trace.add("tool", "error", chosen.get("name", "?"), f"ошибка: {exc}", 0)
        _obj, preview, tool_name = tools.execute_tool(
            db, message, analysis, "ask_clarification", {}
        )
    trace.add(
        "tool", tool_name,
        chosen.get("arguments") or {},
        preview,
        int((time.perf_counter() - t0) * 1000),
    )

    # Уточняющее письмо тоже уходит пользователю, поэтому проверяется.
    # Здесь достаточно программного слоя: вопросы должны опираться на текст
    # обращения, а выдуманных телефонов и сроков в них быть не может.
    if tool_name == "ask_clarification" and verdict is None:
        letter = next((o for o in message.outbox if o.status == "draft"), None)
        if letter is not None:
            t0 = time.perf_counter()
            verdict = roles.verify_answer(
                client, letter.body, passages, message.body,
                use_model=False, mode="questions",
            )
            analysis.verification = verdict.as_dict()
            letter.verification = verdict.as_dict()
            letter.sources = passages
            db.commit()
            trace.add(
                "tool", "verify_answer",
                "проверка уточняющего письма",
                f"{verdict.status}, оценка {verdict.score:.2f}, нарушений {len(verdict.issues)}",
                int((time.perf_counter() - t0) * 1000),
            )

    analysis.suggested_action = tool_name
    analysis.action_reason = _action_reason(tool_name, extracted, similar, kb, mass, verdict)

    _route(db, message, analysis, verdict, tool_name, extracted)
    analysis.similar_ticket_ids = [item["id"] for item in similar]
    analysis.kb_article_ids = analysis.kb_article_ids or [item["id"] for item in kb]
    analysis.mass_incident = mass
    analysis.latency_ms = int((time.perf_counter() - started) * 1000)
    db.commit()

    trace.flush()
    db.commit()
    db.refresh(analysis)
    return analysis


def _action_reason(action: str, extracted: dict, similar: list, kb: list,
                   mass: bool, verdict=None) -> str:
    if verdict is not None and verdict.status not in ("verified", "needs_review"):
        return (
            "Черновик ответа не прошёл проверку на искажения, поэтому вместо "
            "отправки готового текста обращение передаётся человеку."
        )
    if action == "draft_reply" and verdict is not None:
        title = kb[0]["title"] if kb else "база знаний"
        return (
            f"Решение описано в источнике «{title}». Ответ проверен: "
            f"{verdict.checks.get('cited_share', 0):.0%} утверждений подтверждены источниками."
        )
    if action == "ask_clarification":
        fields = ", ".join(item["field"] for item in extracted["missing_fields"]) or "деталей"
        return f"В обращении не хватает данных: {fields}. Без них исполнитель не сможет начать."
    if action == "draft_reply":
        title = kb[0]["title"] if kb else "инструкция базы знаний"
        return f"Решение описано в базе знаний: «{title}». Заявка не нужна."
    parts = ["Данных достаточно, чтобы исполнитель начал работу."]
    if similar:
        parts.append(f"Есть похожая заявка {similar[0]['key']}.")
    if mass:
        parts.append("Поднят признак возможного массового сбоя.")
    return " ".join(parts)


# --- маршрутизация: что уходит само, а что человеку ------------------------


def _route(db: Session, message: Message, analysis: Analysis, verdict,
           tool_name: str, extracted: dict) -> None:
    """Решает, отправить результат сразу или передать человеку.

    Подтверждать каждое письмо человеком слишком медленно: пользователь ждёт
    ответа, пока оператор разгребает очередь. Поэтому человек здесь разбирает
    исключения, а не визирует поток. Проверенный ответ уходит сам, а всё,
    к чему проверка предъявила претензии, останавливается и ждёт человека.
    """
    reason = _human_reason(verdict, tool_name, extracted, analysis.model)

    if not settings.auto_send or reason:
        analysis.auto_sent = False
        analysis.human_reason = reason or "Автоотправка выключена в настройках"
        message.status = "analyzed"
        db.commit()
        return

    for letter in message.outbox:
        if letter.status == "draft":
            letter.status = "sent"
    for ticket in message.tickets:
        if ticket.status == "proposed":
            ticket.status = "waiting_user" if tool_name == "ask_clarification" else "open"

    analysis.auto_sent = True
    analysis.human_reason = ""
    message.status = "processed"
    db.commit()


def _human_reason(verdict, tool_name: str, extracted: dict, model: str = "") -> str:
    """Пустая строка означает, что вмешательство человека не требуется."""
    if verdict is not None and verdict.status != "verified":
        return {
            "needs_review": "Проверка подтвердила не все утверждения ответа",
            "rejected": "Ответ не прошёл проверку на искажения и не был отправлен",
            "insufficient": "В базе знаний нет подходящего материала для ответа",
        }.get(verdict.status, "Проверка ответа завершилась с замечаниями")

    if (
        extracted.get("confidence", 1.0) < 0.6
        and tool_name != "ask_clarification"
        and model != "mock"
    ):
        # У заглушки уверенность — константа 0.5, а не оценка: применять к ней
        # этот порог значит останавливать вообще всё и показывать неработающий
        # продукт тому, кто запустил проект без ключа модели.
        #
        # Неуверенный разбор опасен, когда мы что-то утверждаем или кого-то
        # нагружаем заявкой. Задать уточняющий вопрос при этом безопасно:
        # худшее, что случится, — человек ответит на лишний вопрос.
        # Останавливать здесь означало бы заставить его ждать вместо ответа.
        return "Модель не уверена в разборе обращения"

    if extracted.get("priority") == "P1":
        return "Критический приоритет: решение принимает человек"

    if tool_name == "create_ticket" and verdict is None:
        # Заявка не содержит текста для пользователя, проверять в ней нечего,
        # но маршрутизация по команде остаётся решением человека при высоком
        # приоритете. В остальных случаях заявка уходит в работу сама.
        return ""

    return ""
