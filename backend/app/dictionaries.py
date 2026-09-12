"""Справочники. Единственное место, где живут коды и русские подписи."""

CATEGORIES = [
    {"code": "access", "label": "Доступы и учётные записи"},
    {"code": "vpn", "label": "VPN и удалённый доступ"},
    {"code": "network", "label": "Сеть и Wi-Fi"},
    {"code": "hardware", "label": "Оборудование"},
    {"code": "software", "label": "Программное обеспечение"},
    {"code": "platform", "label": "Корпоративные и учебные платформы"},
    {"code": "email", "label": "Почта и календарь"},
    {"code": "docs", "label": "Документы и оплаты"},
    {"code": "other", "label": "Прочее"},
]

PRIORITIES = [
    {"code": "P1", "label": "Критический"},
    {"code": "P2", "label": "Высокий"},
    {"code": "P3", "label": "Обычный"},
    {"code": "P4", "label": "Низкий"},
]

TEAMS = [
    {"code": "l1_support", "label": "Первая линия"},
    {"code": "access_team", "label": "Команда доступов"},
    {"code": "network_team", "label": "Сетевая команда"},
    {"code": "hardware_team", "label": "Команда оборудования"},
    {"code": "apps_team", "label": "Команда приложений"},
    {"code": "platform_team", "label": "Команда платформы"},
    {"code": "security", "label": "Информационная безопасность"},
]

ACTIONS = [
    {"code": "create_ticket", "label": "Создать заявку"},
    {"code": "ask_clarification", "label": "Запросить уточнение"},
    {"code": "draft_reply", "label": "Черновик ответа"},
]

SENTIMENTS = [
    {"code": "calm", "label": "Спокойное"},
    {"code": "annoyed", "label": "Раздражённое"},
    {"code": "angry", "label": "Резкое"},
]

CHANNELS = [
    {"code": "email", "label": "Письмо"},
    {"code": "call", "label": "Звонок"},
]

MESSAGE_STATUSES = [
    {"code": "new", "label": "Новое"},
    {"code": "analyzed", "label": "Разобрано"},
    {"code": "processed", "label": "Обработано"},
]

TICKET_STATUSES = [
    {"code": "proposed", "label": "Предложена агентом"},
    {"code": "open", "label": "В работе"},
    {"code": "waiting_user", "label": "Ждём пользователя"},
    {"code": "closed", "label": "Закрыта"},
    {"code": "rejected", "label": "Отклонена"},
]

STEP_NAMES = {
    "extract_structure": "Разбор обращения моделью",
    "search_similar_tickets": "Поиск похожих заявок",
    "search_knowledge_base": "Поиск в базе знаний",
    "decide_action": "Выбор действия моделью",
    "create_ticket": "Создание заявки",
    "ask_clarification": "Подготовка уточнения",
    "draft_reply": "Подготовка ответа",
    "error": "Ошибка прогона",
}


def _codes(items: list[dict]) -> set[str]:
    return {item["code"] for item in items}


CATEGORY_CODES = _codes(CATEGORIES)
PRIORITY_CODES = _codes(PRIORITIES)
TEAM_CODES = _codes(TEAMS)
ACTION_CODES = _codes(ACTIONS)
SENTIMENT_CODES = _codes(SENTIMENTS)
CHANNEL_CODES = _codes(CHANNELS)
TICKET_STATUS_CODES = _codes(TICKET_STATUSES)


def label_of(items: list[dict], code: str) -> str:
    """Русская подпись по коду. Неизвестный код возвращается как есть."""
    for item in items:
        if item["code"] == code:
            return item["label"]
    return code


def safe(code: str | None, allowed: set[str], default: str) -> str:
    """Подстановка безопасного значения, если модель вернула что-то своё."""
    if isinstance(code, str) and code in allowed:
        return code
    return default


def as_payload() -> dict:
    return {
        "categories": CATEGORIES,
        "priorities": PRIORITIES,
        "teams": TEAMS,
        "actions": ACTIONS,
        "sentiments": SENTIMENTS,
        "channels": CHANNELS,
        "message_statuses": MESSAGE_STATUSES,
        "ticket_statuses": TICKET_STATUSES,
        "step_names": STEP_NAMES,
    }
