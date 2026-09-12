"""Проверка ответа на искажения и выдумки.

Замысел. Ответ помощника считается пригодным только тогда, когда каждое
утверждение в нём опирается на переданный моделью фрагмент базы знаний
или на текст самого обращения. Всё остальное — выдумка, даже если звучит
правдоподобно.

Проверка идёт в два слоя.

Первый слой — обычный код, работает за миллисекунды и не зависит от модели:
разрешаются ли ссылки, откуда взялись числа, коды ошибок, телефоны и адреса,
не появились ли обещания сроков, которых нет в источниках.

Второй слой — отдельный вызов модели, которая разбирает ответ на утверждения
и для каждого говорит, подтверждается оно источниками или нет. Он включается
только для черновиков ответа пользователю, то есть там, где цена выдумки
наибольшая.

Детерминированный слой намеренно первый: он ловит самый опасный класс ошибок
(выдуманный номер телефона, несуществующий срок) без обращения к модели,
а значит быстро и одинаково при каждом запуске.
"""
import re
from dataclasses import dataclass, field

from app.rag.tokens import tokenize

# --- что ищем в тексте --------------------------------------------------

CITATION = re.compile(r"\[(\d{1,2})\]")
NUMBER = re.compile(r"(?<![\w./-])\d{1,4}(?:[.,]\d+)?(?![\w/-])")
ERROR_CODE = re.compile(r"\b[A-Z][A-Z0-9]{2,}(?:_[A-Z0-9]+)+\b")
PHONE = re.compile(r"(?:\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}")
EMAIL = re.compile(r"[\w.-]+@[\w.-]+\.[a-zA-Zа-яА-Я]{2,}")
URL = re.compile(r"(?:https?://|www\.)[^\s,)]+")
UNC_PATH = re.compile(r"\\\\[\w.$-]+(?:\\[\w.$-]+)+")

# Обещания, которых модель не имеет права давать от своего имени
PROMISES = [
    (re.compile(r"\bв течение\s+\d+\s*(?:минут|часов|часа|дней|дня|рабочих)", re.I), "срок исполнения"),
    (re.compile(r"\b(?:гарантирую|гарантируем|обязательно поможет|точно решит|100%)", re.I), "гарантия результата"),
    (re.compile(r"\b(?:бесплатно|без оплаты|компенсируем|возместим)", re.I), "обещание об оплате"),
    (re.compile(r"\bне позднее\s+\w+", re.I), "крайний срок"),
]

# Точка после цифры — это маркер пункта списка, а не конец предложения.
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])(?<!\d\.)\s+")
LIST_ITEM = re.compile(r"^\s*(?:\d{1,2}[.)]|[-–—•])\s+")

# Вежливость и служебные строки утверждениями не являются: проверять в них нечего.
BOILERPLATE = re.compile(
    r"^(здравствуйте|добрый день|спасибо|с уважением|служба технической поддержки|"
    r"если .{0,80}(не помог|останется|возникн|потребу)|будем рады|хорошего дня|"
    r"по вашему (обращению|вопросу) есть|вот что можно (сделать|проверить)|"
    r"ниже .{0,40}(инструкц|шаг)|проверьте, пожалуйста, следующее)",
    re.I,
)

WEIGHTS = {
    "citations": 0.25,
    "facts": 0.35,
    "coverage": 0.20,
    "promises": 0.20,
}


@dataclass
class Issue:
    kind: str
    severity: str
    fragment: str
    explanation: str

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "fragment": self.fragment,
            "explanation": self.explanation,
        }


@dataclass
class Verdict:
    status: str
    score: float
    checks: dict = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)
    claims: list[dict] = field(default_factory=list)
    model_used: bool = False
    latency_ms: int = 0

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "score": round(self.score, 3),
            "checks": self.checks,
            "issues": [issue.as_dict() for issue in self.issues],
            "claims": self.claims,
            "model_used": self.model_used,
            "latency_ms": self.latency_ms,
        }


def split_sentences(text: str) -> list[str]:
    """Утверждение — это пункт списка целиком или отдельное предложение.

    Пункт нумерованной инструкции не режется на части: «1. Откройте настройки [1]»
    должно остаться одним утверждением вместе со своей ссылкой, иначе ссылка
    отрывается от того, что она подтверждает.
    """
    statements: list[str] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if LIST_ITEM.match(line):
            statements.append(line)
            continue
        statements.extend(part.strip() for part in SENTENCE_SPLIT.split(line))
    return [s for s in statements if s and not BOILERPLATE.match(s)]


def _strip_citations(text: str) -> str:
    return CITATION.sub(" ", text)


def check_deterministic(answer: str, passages: list[dict], message_body: str) -> Verdict:
    """Первый слой: всё, что можно проверить без обращения к модели."""
    sources_text = "\n".join(p.get("text", "") for p in passages)
    grounded_text = f"{sources_text}\n{message_body}"
    source_tokens = set(tokenize(sources_text)) | set(tokenize(message_body))

    issues: list[Issue] = []
    sentences = split_sentences(answer)

    # 1. Ссылки указывают на реально переданные фрагменты
    valid_ids = set(range(1, len(passages) + 1))
    used = {int(n) for n in CITATION.findall(answer)}
    broken = sorted(used - valid_ids)
    for number in broken:
        issues.append(
            Issue(
                "broken_citation",
                "critical",
                f"[{number}]",
                f"Ссылка [{number}] указывает на источник, которого нет. "
                f"Передано фрагментов: {len(passages)}",
            )
        )
    citation_score = 0.0 if broken else (1.0 if used else 0.3)

    # 2. Утверждения без ссылки на источник.
    # Вопрос — не утверждение: спрашивая, помощник ничего не заявляет,
    # поэтому ссылка на источник от вопроса не требуется.
    statements = [s for s in sentences if not s.rstrip().endswith("?")]
    unsupported = [s for s in statements if not CITATION.search(s)]
    if statements:
        supported_share = 1 - len(unsupported) / len(statements)
    elif sentences:
        supported_share = 1.0  # в письме одни вопросы, проверять нечего
    else:
        supported_share = 0.0
    for sentence in unsupported[:5]:
        issues.append(
            Issue(
                "uncited_claim",
                "warning",
                sentence[:160],
                "Утверждение не сопровождается ссылкой на источник",
            )
        )

    # 3. Факты: числа, коды, контакты, пути — только из источников или обращения
    fact_issues = _check_facts(answer, grounded_text)
    issues.extend(fact_issues)
    facts_score = 1.0 if not fact_issues else max(0.0, 1 - 0.34 * len(fact_issues))

    # 4. Лексическое покрытие: насколько ответ держится текста источников
    answer_tokens = set(tokenize(_strip_citations(answer)))
    coverage = (
        len(answer_tokens & source_tokens) / len(answer_tokens) if answer_tokens else 0.0
    )
    if coverage < 0.45 and answer_tokens:
        issues.append(
            Issue(
                "low_coverage",
                "warning",
                f"{coverage:.0%}",
                "Больше половины значимых слов ответа не встречаются ни в источниках, "
                "ни в обращении. Похоже на свободный пересказ",
            )
        )

    # 5. Обещания, которых нет в источниках
    promise_issues = []
    for pattern, label in PROMISES:
        for match in pattern.findall(answer):
            fragment = match if isinstance(match, str) else str(match)
            if fragment.lower() in sources_text.lower():
                continue
            promise_issues.append(
                Issue(
                    "unsupported_promise",
                    "critical",
                    fragment[:120],
                    f"В ответе появилось обещание ({label}), которого нет в источниках",
                )
            )
    issues.extend(promise_issues)
    promises_score = 0.0 if promise_issues else 1.0

    score = (
        WEIGHTS["citations"] * citation_score
        + WEIGHTS["facts"] * facts_score
        + WEIGHTS["coverage"] * min(coverage / 0.6, 1.0)
        + WEIGHTS["promises"] * promises_score
    )
    # Доля утверждений со ссылкой влияет как множитель: ответ, где половина
    # предложений висит в воздухе, не может считаться проверенным.
    score *= 0.5 + 0.5 * supported_share

    return Verdict(
        status=status_for(score, issues),
        score=score,
        checks={
            "citations_valid": not broken,
            "cited_share": round(supported_share, 2),
            "questions": len(sentences) - len(statements),
            "facts_grounded": not fact_issues,
            "lexical_coverage": round(coverage, 2),
            "no_unsupported_promises": not promise_issues,
            "sentences": len(sentences),
            "sources": len(passages),
        },
        issues=issues,
    )


def _check_facts(answer: str, grounded_text: str) -> list[Issue]:
    """Числа и контакты в ответе обязаны встречаться в источниках."""
    issues: list[Issue] = []
    haystack = grounded_text.lower()
    clean = _strip_citations(answer)

    checks = [
        (ERROR_CODE, "invented_code", "critical", "Код ошибки"),
        (PHONE, "invented_contact", "critical", "Номер телефона"),
        (EMAIL, "invented_contact", "critical", "Адрес почты"),
        (URL, "invented_contact", "critical", "Ссылка"),
        (UNC_PATH, "invented_path", "critical", "Сетевой путь"),
    ]
    for pattern, kind, severity, label in checks:
        for found in set(pattern.findall(clean)):
            if found.lower() not in haystack:
                issues.append(
                    Issue(
                        kind,
                        severity,
                        found,
                        f"{label} «{found}» не встречается ни в источниках, ни в обращении",
                    )
                )

    # Числа проверяем мягче: нумерация шагов в ответе законна
    numbered_steps = set(re.findall(r"^\s*(\d{1,2})[.)]\s", clean, flags=re.M))
    for found in set(NUMBER.findall(clean)):
        if found in numbered_steps or len(found) < 2:
            continue
        if found not in haystack:
            issues.append(
                Issue(
                    "invented_number",
                    "warning",
                    found,
                    f"Число «{found}» не встречается ни в источниках, ни в обращении",
                )
            )
    return issues


def status_for(score: float, issues: list[Issue]) -> str:
    if any(issue.severity == "critical" for issue in issues):
        return "rejected"
    if score >= 0.85:
        return "verified"
    if score >= 0.6:
        return "needs_review"
    return "rejected"
