"""Правила заглушки. Осмысленные ответы по ключевым словам, а не случайные."""

RULES = [
    {
        "keys": ["vpn", "туннель", "tunnel", "удалён", "удален"],
        "category": "vpn",
        "service": "Корпоративный VPN",
        "priority": "P2",
        "team": "network_team",
        "action": "create_ticket",
    },
    {
        "keys": ["пароль", "заблокир", "учётн", "учетн", "не пускает", "войти", "не впускает"],
        "category": "access",
        "service": "Учётная запись домена",
        "priority": "P2",
        "team": "access_team",
        "action": "ask_clarification",
    },
    {
        "keys": ["wi-fi", "wifi", "вайфай", "сеть", "интернет"],
        "category": "network",
        "service": "Wi-Fi",
        "priority": "P1",
        "team": "network_team",
        "action": "create_ticket",
    },
    {
        "keys": ["принтер", "печат", "картридж"],
        "category": "hardware",
        "service": "Печать",
        "priority": "P3",
        "team": "hardware_team",
        "action": "create_ticket",
    },
    {
        "keys": ["не включается", "монитор", "мышь", "клавиатур", "зарядк"],
        "category": "hardware",
        "service": "Рабочая станция",
        "priority": "P2",
        "team": "hardware_team",
        "action": "create_ticket",
    },
    {
        "keys": ["почт", "outlook", "календар", "встреч"],
        "category": "email",
        "service": "Почта и календарь",
        "priority": "P3",
        "team": "apps_team",
        "action": "draft_reply",
    },
    {
        "keys": ["курс", "платформ", "обучен", "лмс"],
        "category": "platform",
        "service": "Учебная платформа",
        "priority": "P2",
        "team": "platform_team",
        "action": "create_ticket",
    },
    {
        "keys": ["папк", "доступ", "отказано"],
        "category": "access",
        "service": "Файловый сервер",
        "priority": "P3",
        "team": "access_team",
        "action": "create_ticket",
    },
    {
        "keys": ["установ", "лицензи", "программ", "figma", "1с"],
        "category": "software",
        "service": "Программное обеспечение",
        "priority": "P4",
        "team": "l1_support",
        "action": "draft_reply",
    },
]

DEFAULT_RULE = {
    "category": "other",
    "service": "Не определён",
    "priority": "P3",
    "team": "l1_support",
    "action": "ask_clarification",
}

ENTITY_PATTERNS = {
    "login": r"(?:логин|login)[^A-Za-z]{0,20}([A-Za-z][A-Za-z0-9._-]*[A-Za-z0-9])",
    "error_code": r"\b(ERR[_A-Z0-9]+|[A-Z]{3,}_[A-Z_]{3,})\b",
    "os": r"\b(Windows\s?\d+|macOS[\w\s.]{0,8}|Android|iOS)\b",
    "browser": r"\b(Chrome|Safari|Firefox|Edge)\b",
    "inventory_number": r"инвентарн\w*\s*(?:номер)?\s*([0-9]{4,8})",
    "location": r"(корпус[а-я]*\s+[А-ЯA-Z]|аудитори[яи]\s*\d+|кабинет\s*\d+)",
}


def match_rule(text: str) -> dict:
    lowered = text.lower()
    for rule in RULES:
        if any(key in lowered for key in rule["keys"]):
            return rule
    return DEFAULT_RULE
