"""Именованные роли агента.

Роли разделены сознательно: у каждой свой промпт, свой вход и своя зона
ответственности. Автор ответа не проверяет сам себя — это делает отдельная
роль с противоположной установкой: искать, за что зацепиться, а не защищать
написанное.
"""
import json
import time

from app.agent import verifier
from app.config import settings
from app.dictionaries import label_of, CATEGORIES, PRIORITIES
from app.llm import prompts

MAX_REPAIRS = 1


def format_sources(passages: list[dict]) -> str:
    """Нумерация фрагментов в том виде, в котором на них ссылается ответ."""
    lines = []
    for number, passage in enumerate(passages, start=1):
        origin = passage.get("source") or "демонстрационная статья"
        lines.append(
            f"[{number}] {passage.get('title', '')}\n"
            f"источник: {origin}\n"
            f"{passage.get('text', '')}"
        )
    return "\n\n".join(lines) if lines else "Фрагментов не найдено."


def format_analysis(analysis: dict) -> str:
    entities = analysis.get("entities") or {}
    return json.dumps(
        {
            "суть": analysis.get("summary"),
            "категория": label_of(CATEGORIES, analysis.get("category", "")),
            "приоритет": label_of(PRIORITIES, analysis.get("priority", "")),
            "известные данные": entities,
            "чего не хватает": [m.get("field") for m in analysis.get("missing_fields", [])],
        },
        ensure_ascii=False,
        indent=2,
    )


def compose_answer(client, message, analysis: dict, passages: list[dict],
                   repair_issues: str | None = None) -> tuple[dict, int]:
    system = prompts.SYSTEM_COMPOSE
    if repair_issues:
        system = system + prompts.REPAIR_SUFFIX.format(issues=repair_issues)

    user = prompts.USER_COMPOSE_TEMPLATE.format(
        body=message.body,
        analysis=format_analysis(analysis),
        sources=format_sources(passages),
    )
    raw, ms = client.complete_json(
        system,
        user,
        prompts.COMPOSE_SCHEMA,
        context={
            "kind": "compose",
            "analysis": analysis,
            "passages": passages,
            "body": message.body,
        },
    )
    return _clean_compose(raw, len(passages)), ms


def _clean_compose(raw: dict, source_count: int) -> dict:
    if not isinstance(raw, dict):
        raw = {}
    answer = str(raw.get("answer") or "").strip()
    insufficient = bool(raw.get("insufficient")) or not answer

    used = []
    for value in raw.get("used_sources") or []:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= number <= source_count:
            used.append(number)

    try:
        confidence = min(max(float(raw.get("confidence", 0.5)), 0.0), 1.0)
    except (TypeError, ValueError):
        confidence = 0.5

    return {
        "answer": answer,
        "used_sources": sorted(set(used)),
        "insufficient": insufficient,
        "confidence": round(confidence, 2),
        "missing_info": str(raw.get("missing_info") or "").strip(),
    }


def verify_with_model(client, answer: str, passages: list[dict]) -> tuple[dict, int]:
    user = prompts.USER_VERIFY_TEMPLATE.format(
        sources=format_sources(passages), answer=answer
    )
    raw, ms = client.complete_json(
        prompts.SYSTEM_VERIFY,
        user,
        prompts.VERIFY_SCHEMA,
        context={"kind": "verify", "answer": answer, "passages": passages},
    )
    claims = []
    for item in (raw or {}).get("claims") or []:
        if not isinstance(item, dict):
            continue
        verdict = item.get("verdict")
        if verdict not in ("supported", "contradicted", "not_found"):
            verdict = "not_found"
        source = item.get("source")
        if not isinstance(source, int) or not (1 <= source <= len(passages)):
            source = None
        claims.append(
            {
                "text": str(item.get("text", ""))[:400],
                "verdict": verdict,
                "source": source,
                "comment": str(item.get("comment", ""))[:300],
            }
        )
    return {"claims": claims}, ms


def verify_answer(client, answer: str, passages: list[dict], message_body: str,
                  use_model: bool = True, mode: str = "answer") -> verifier.Verdict:
    """Два слоя проверки. Код — всегда, модель — когда цена ошибки высока."""
    started = time.perf_counter()
    verdict = verifier.check_deterministic(answer, passages, message_body, mode=mode)

    if not use_model or verdict.status == "rejected":
        # Если детерминированный слой уже отверг ответ, звать модель незачем:
        # решение не изменится, а время потратится.
        verdict.latency_ms = int((time.perf_counter() - started) * 1000)
        return verdict

    try:
        model_result, _ms = verify_with_model(client, answer, passages)
    except Exception:  # noqa: BLE001  проверка не должна ронять прогон
        verdict.latency_ms = int((time.perf_counter() - started) * 1000)
        return verdict

    claims = model_result["claims"]
    verdict.claims = claims
    verdict.model_used = True

    if claims:
        bad = [c for c in claims if c["verdict"] != "supported"]
        for claim in bad[:5]:
            verdict.issues.append(
                verifier.Issue(
                    "model_" + claim["verdict"],
                    "critical" if claim["verdict"] == "contradicted" else "warning",
                    claim["text"][:160],
                    claim["comment"] or "Проверяющий не нашёл подтверждения в источниках",
                )
            )
        supported_share = 1 - len(bad) / len(claims)
        verdict.checks["model_supported_share"] = round(supported_share, 2)
        verdict.checks["model_claims"] = len(claims)
        # Итог: среднее между слоями, но вес детерминированного выше,
        # потому что он проверяет факты, а не правдоподобие.
        verdict.score = 0.6 * verdict.score + 0.4 * supported_share
        verdict.status = verifier.status_for(verdict.score, verdict.issues)

    verdict.latency_ms = int((time.perf_counter() - started) * 1000)
    return verdict


def compose_and_verify(client, message, analysis: dict, passages: list[dict],
                       trace) -> tuple[dict, verifier.Verdict]:
    """Сгенерировать, проверить, при провале один раз переписать с указанием ошибок."""
    draft, ms = compose_answer(client, message, analysis, passages)
    trace.add(
        "llm", "compose_answer",
        f"фрагментов: {len(passages)}",
        "нечем ответить" if draft["insufficient"] else draft["answer"][:200],
        ms,
    )

    if draft["insufficient"]:
        empty = verifier.Verdict(status="insufficient", score=0.0)
        empty.checks = {"sources": len(passages)}
        return draft, empty

    verdict = verify_answer(
        client, draft["answer"], passages, message.body,
        use_model=settings.verify_with_model,
    )
    trace.add(
        "llm" if verdict.model_used else "tool", "verify_answer",
        f"предложений: {verdict.checks.get('sentences', 0)}",
        f"{verdict.status}, оценка {verdict.score:.2f}, нарушений {len(verdict.issues)}",
        verdict.latency_ms,
    )

    attempts = 0
    while verdict.status == "rejected" and attempts < MAX_REPAIRS:
        attempts += 1
        issues_text = "\n".join(
            f"- {issue.explanation} (фрагмент: {issue.fragment})"
            for issue in verdict.issues[:8]
        )
        draft, ms = compose_answer(
            client, message, analysis, passages, repair_issues=issues_text
        )
        trace.add(
            "llm", "compose_answer",
            f"переписывание после проверки, попытка {attempts}",
            "нечем ответить" if draft["insufficient"] else draft["answer"][:200],
            ms,
        )
        if draft["insufficient"]:
            verdict = verifier.Verdict(status="insufficient", score=0.0)
            verdict.checks = {"sources": len(passages)}
            break
        verdict = verify_answer(
            client, draft["answer"], passages, message.body,
            use_model=settings.verify_with_model,
        )
        trace.add(
            "llm" if verdict.model_used else "tool", "verify_answer",
            f"повторная проверка, попытка {attempts}",
            f"{verdict.status}, оценка {verdict.score:.2f}, нарушений {len(verdict.issues)}",
            verdict.latency_ms,
        )

    return draft, verdict
