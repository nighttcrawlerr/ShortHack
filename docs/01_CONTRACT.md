# Контракт: схема данных, API, LLM

Этот файл читают оба разработчика перед первой строкой кода.
Изменения только по согласованию обоих.

---

## 1. Справочники

Бэкенд отдаёт их на `GET /api/dictionaries`. Фронтенд не хардкодит подписи.

### Категории (`category`)

| Код | Подпись |
|---|---|
| `access` | Доступы и учётные записи |
| `vpn` | VPN и удалённый доступ |
| `network` | Сеть и Wi-Fi |
| `hardware` | Оборудование |
| `software` | Программное обеспечение |
| `platform` | Корпоративные и учебные платформы |
| `email` | Почта и календарь |
| `docs` | Документы и оплаты |
| `other` | Прочее |

### Приоритеты (`priority`)

| Код | Подпись | Когда назначать |
|---|---|---|
| `P1` | Критический | Полная остановка работы группы людей или сервиса целиком |
| `P2` | Высокий | Один человек полностью заблокирован в работе, обхода нет |
| `P3` | Обычный | Работать можно, но неудобно, есть обходной путь |
| `P4` | Низкий | Вопрос, консультация, пожелание |

### Команды (`team`)

`l1_support`, `access_team`, `network_team`, `hardware_team`, `apps_team`, `platform_team`, `security`

### Действия агента (`action`)

| Код | Подпись | Когда выбирать |
|---|---|---|
| `create_ticket` | Создать заявку | Данных достаточно, чтобы исполнитель начал работу |
| `ask_clarification` | Запросить уточнение | Не хватает данных, без которых заявку нельзя маршрутизировать или решить |
| `draft_reply` | Черновик ответа | Ответ есть в базе знаний, заявка не нужна |

### Статусы

- Обращение (`messages.status`): `new`, `analyzed`, `processed`
- Заявка (`tickets.status`): `proposed`, `open`, `waiting_user`, `closed`, `rejected`

---

## 2. Схема базы данных

SQLite, файл `backend/saluteagent.db`. Поля с пометкой JSON хранятся как текст и сериализуются в Python.

### `messages` — входящее обращение

| Поле | Тип | Описание |
|---|---|---|
| `id` | int PK | |
| `channel` | str | `email` или `call` |
| `subject` | str? | Тема письма, у звонков `null` |
| `author_name` | str | Кто обратился |
| `author_email` | str | |
| `received_at` | str | ISO 8601 |
| `body` | text | Текст письма или расшифровка разговора |
| `status` | str | `new` / `analyzed` / `processed` |
| `created_at` | str | ISO 8601 |

### `analyses` — результат разбора

| Поле | Тип | Описание |
|---|---|---|
| `id` | int PK | |
| `message_id` | int FK | |
| `summary` | text | Одно-два предложения |
| `intents` | JSON | Список отдельных вопросов внутри обращения |
| `category` | str | Код из справочника |
| `service` | str | Название сервиса свободным текстом |
| `priority` | str | `P1`–`P4` |
| `priority_reason` | text | Почему такой приоритет |
| `team` | str | Код команды |
| `entities` | JSON | Объект извлечённых данных |
| `missing_fields` | JSON | Список объектов, чего не хватает |
| `sentiment` | str | `calm` / `annoyed` / `angry` |
| `confidence` | float | 0.0–1.0 |
| `suggested_action` | str | Код действия |
| `action_reason` | text | Почему это действие |
| `similar_ticket_ids` | JSON | Список id похожих заявок |
| `kb_article_ids` | JSON | Список id статей базы знаний |
| `mass_incident` | bool | Признак возможного массового сбоя |
| `model` | str | Имя модели или `mock` |
| `latency_ms` | int | Время полного прогона |
| `raw_llm` | JSON | Сырой ответ модели, для отладки |
| `created_at` | str | |

### `tickets` — заявка

| Поле | Тип | Описание |
|---|---|---|
| `id` | int PK | |
| `key` | str | Человеческий номер, `SD-1001` |
| `message_id` | int? FK | |
| `title` | str | |
| `description` | text | |
| `category`, `service`, `priority`, `team` | str | |
| `status` | str | См. справочник |
| `requester_name`, `requester_email` | str | |
| `entities` | JSON | |
| `resolution` | text? | Как решили, для закрытых демо-заявок |
| `created_by` | str | `agent` или `operator` |
| `created_at`, `updated_at` | str | |

### `kb_articles` — база знаний

| Поле | Тип |
|---|---|
| `id` | int PK |
| `title` | str |
| `category` | str |
| `service` | str |
| `keywords` | JSON, список строк |
| `body` | text |

### `agent_steps` — трасса работы агента

| Поле | Тип | Описание |
|---|---|---|
| `id` | int PK | |
| `message_id` | int FK | |
| `step_no` | int | Порядковый номер, с 1 |
| `kind` | str | `llm` или `tool` |
| `name` | str | `extract_structure`, `search_similar_tickets`, `search_knowledge_base`, `decide_action`, `create_ticket`, `ask_clarification`, `draft_reply` |
| `input_preview` | text | Короткая выжимка входа, до 500 символов |
| `output_preview` | text | Короткая выжимка выхода, до 500 символов |
| `latency_ms` | int | |
| `created_at` | str | |

### `outbox` — подготовленные тексты для пользователя

| Поле | Тип | Описание |
|---|---|---|
| `id` | int PK | |
| `message_id` | int FK | |
| `ticket_id` | int? FK | |
| `kind` | str | `clarification` или `reply` |
| `subject` | str | |
| `body` | text | |
| `status` | str | `draft` или `sent` |
| `created_at` | str | |

---

## 3. Формы объектов в JSON

Эти формы одинаковы в ответах API и в типах фронтенда.

### `entities`

Все поля необязательные, отсутствующие не включаются.

```json
{
  "login": "ivanov.ii",
  "full_name": "Иванов Иван Иванович",
  "email": "ivanov@example.ru",
  "phone": "+7 900 000-00-00",
  "employee_id": "12345",
  "service_name": "VPN",
  "device": "ноутбук Lenovo T14",
  "os": "Windows 11",
  "browser": "Chrome 128",
  "error_code": "ERR_TUNNEL_FAILED",
  "occurred_at": "сегодня утром, около 9:30",
  "location": "корпус Б, аудитория 405"
}
```

### `missing_fields`

```json
[
  {
    "field": "login",
    "why": "Без логина нельзя найти учётную запись и сбросить пароль",
    "question": "Подскажите, пожалуйста, ваш корпоративный логин."
  }
]
```

### `intents`

```json
["Не открывается VPN", "Запрос на доступ к общей папке отдела"]
```

---

## 4. HTTP API

База: `http://localhost:8000`. Все ответы `application/json`, кодировка UTF-8, `ensure_ascii=False`.
Ошибки в формате `{"detail": "текст"}` с кодами 400, 404, 500, 503.

CORS: разрешить `http://localhost:5173`.

### `GET /api/health`

```json
{ "status": "ok", "llm": "live", "model": "gpt-4o-mini", "db_messages": 12 }
```

Поле `llm`: `live`, если ключ есть и последний вызов прошёл; `mock`, если работаем на заглушке; `error`, если ключ есть, но вызовы падают. Фронт показывает это индикатором в шапке.

### `GET /api/dictionaries`

```json
{
  "categories": [{ "code": "access", "label": "Доступы и учётные записи" }],
  "priorities": [{ "code": "P1", "label": "Критический" }],
  "teams":      [{ "code": "l1_support", "label": "Первая линия" }],
  "actions":    [{ "code": "create_ticket", "label": "Создать заявку" }]
}
```

### `GET /api/messages`

Параметры: `status` (необязательно), `q` — поиск по теме и телу, `limit` по умолчанию 100.

```json
[
  {
    "id": 1,
    "channel": "email",
    "subject": "Не могу зайти в VPN",
    "author_name": "Иванов И.И.",
    "author_email": "ivanov@example.ru",
    "received_at": "2026-09-12T09:12:00",
    "preview": "Здравствуйте! Со вчерашнего дня не получается...",
    "status": "new",
    "has_analysis": false,
    "category": null,
    "priority": null
  }
]
```

`preview` — первые 160 символов тела. `category` и `priority` заполняются, если разбор уже есть: нужны для цветных меток в списке.

### `GET /api/messages/{id}`

```json
{
  "message": {
    "id": 1, "channel": "email", "subject": "Не могу зайти в VPN",
    "author_name": "Иванов И.И.", "author_email": "ivanov@example.ru",
    "received_at": "2026-09-12T09:12:00", "body": "полный текст",
    "status": "analyzed"
  },
  "analysis": { "...": "объект Analysis или null" },
  "steps": [ { "...": "объект AgentStep" } ],
  "tickets": [ { "...": "объект Ticket" } ],
  "outbox": [ { "...": "объект Outbox" } ]
}
```

### `POST /api/messages`

Создать обращение вручную. Это демонстрационная фишка: на защите можно вставить любой текст.

Запрос:

```json
{
  "channel": "email",
  "subject": "Тема",
  "author_name": "Пётр Петров",
  "author_email": "petrov@example.ru",
  "body": "Текст обращения"
}
```

Ответ: объект `message`, код 201. Поля `subject` и `author_email` необязательны, подставляются значения по умолчанию.

### `POST /api/messages/{id}/analyze`

Главный эндпоинт. Запускает весь агентный прогон синхронно. Тело запроса пустое.

Параметр `?force=true` — перезапустить разбор, даже если он уже есть. Без него повторный вызов возвращает сохранённый результат из базы и не дёргает модель.

Ответ 200:

```json
{
  "analysis": {
    "id": 5,
    "message_id": 1,
    "summary": "Сотрудник не может подключиться к корпоративному VPN со вчерашнего дня, на экране ошибка ERR_TUNNEL_FAILED.",
    "intents": ["Не подключается VPN"],
    "category": "vpn",
    "service": "Корпоративный VPN",
    "priority": "P2",
    "priority_reason": "Сотрудник на удалённой работе полностью заблокирован, обходного пути нет",
    "team": "network_team",
    "entities": { "login": "ivanov.ii", "error_code": "ERR_TUNNEL_FAILED", "os": "Windows 11" },
    "missing_fields": [],
    "sentiment": "annoyed",
    "confidence": 0.86,
    "suggested_action": "create_ticket",
    "action_reason": "Есть логин, код ошибки и операционная система, этого достаточно для сетевой команды",
    "similar_ticket_ids": [3, 7],
    "kb_article_ids": [2],
    "mass_incident": false,
    "model": "gpt-4o-mini",
    "latency_ms": 4120,
    "created_at": "2026-09-12T11:40:00"
  },
  "steps": [
    { "step_no": 1, "kind": "llm",  "name": "extract_structure",       "input_preview": "...", "output_preview": "...", "latency_ms": 2100 },
    { "step_no": 2, "kind": "tool", "name": "search_similar_tickets",  "input_preview": "vpn / Корпоративный VPN", "output_preview": "найдено 2", "latency_ms": 3 },
    { "step_no": 3, "kind": "tool", "name": "search_knowledge_base",   "input_preview": "...", "output_preview": "найдена 1 статья", "latency_ms": 2 },
    { "step_no": 4, "kind": "llm",  "name": "decide_action",           "input_preview": "...", "output_preview": "create_ticket", "latency_ms": 1900 },
    { "step_no": 5, "kind": "tool", "name": "create_ticket",           "input_preview": "...", "output_preview": "SD-1013", "latency_ms": 8 }
  ],
  "tickets": [ { "id": 13, "key": "SD-1013", "status": "proposed", "...": "" } ],
  "outbox": []
}
```

Ошибка 503, если LLM недоступна и запасной режим выключен: `{"detail": "LLM недоступна: <причина>"}`.

### `POST /api/messages/{id}/apply`

Оператор подтверждает или меняет предложение агента.

Запрос:

```json
{
  "decision": "confirm",
  "ticket_id": 13,
  "overrides": { "priority": "P1", "team": "network_team", "category": "vpn" },
  "outbox_id": null,
  "edited_body": null
}
```

- `decision`: `confirm`, `reject`, `edit`.
- `overrides` — необязательный объект, применяется к заявке перед подтверждением.
- `edited_body` — исправленный оператором текст письма, если подтверждается запись из `outbox`.

Поведение:

| decision | Что происходит |
|---|---|
| `confirm` | Заявка `proposed` → `open`, запись outbox `draft` → `sent`, обращение → `processed` |
| `edit` | Применяются `overrides` и `edited_body`, затем то же, что при `confirm` |
| `reject` | Заявка → `rejected`, обращение возвращается в `new` |

Ответ: обновлённый объект как у `GET /api/messages/{id}`.

### `GET /api/tickets`

Параметры: `status`, `category`, `priority`, `q`. Ответ — список объектов `Ticket`.

### `PATCH /api/tickets/{id}`

Тело: любое подмножество полей `status`, `priority`, `category`, `team`, `title`, `description`, `resolution`. Ответ — обновлённая заявка.

### `GET /api/similar?message_id={id}` или `?q={текст}`

```json
[
  { "id": 3, "key": "SD-1003", "title": "VPN не подключается после смены пароля",
    "status": "closed", "resolution": "Сброшен сертификат, переустановлен профиль",
    "score": 0.72 }
]
```

`score` от 0 до 1. Отдавать максимум 5, отсортировано по убыванию.

### `GET /api/kb?q={текст}`

```json
[ { "id": 2, "title": "Ошибка ERR_TUNNEL_FAILED в VPN", "category": "vpn",
    "excerpt": "Первые 200 символов статьи", "score": 0.64 } ]
```

### `GET /api/stats`

Для дашборда. Делается последним.

```json
{
  "messages_total": 12,
  "messages_analyzed": 9,
  "tickets_total": 7,
  "auto_actionable_share": 0.67,
  "avg_latency_ms": 4300,
  "by_category":  [{ "code": "vpn",  "label": "VPN и удалённый доступ", "count": 3 }],
  "by_priority":  [{ "code": "P2",   "label": "Высокий", "count": 4 }],
  "by_action":    [{ "code": "create_ticket", "label": "Создать заявку", "count": 5 }],
  "mass_incidents": [
    { "category": "network", "service": "Wi-Fi", "count": 3,
      "message_ids": [4, 8, 11],
      "hint": "Три обращения по Wi-Fi в корпусе Б за два часа, возможен массовый сбой" }
  ]
}
```

`auto_actionable_share` — доля разборов с `confidence >= 0.7`, где действие не потребовало правок оператора. Это цифра для слайда с эффектом.

### `POST /api/seed`

Стирает базу и перезаливает данные из `data/seed_messages.json` и `data/kb_articles.json`.
Ответ: `{ "messages": 12, "kb_articles": 8, "tickets": 6 }`.
Нужен, чтобы за минуту до защиты вернуть чистое состояние.

---

## 5. Работа с LLM

### Переменные окружения

Файл `backend/.env`, пример коммитим как `.env.example`.

```
LLM_PROVIDER=openai        # openai | gigachat | mock
LLM_BASE_URL=https://...   # выдадут организаторы
LLM_API_KEY=...            # выдадут организаторы
LLM_MODEL=...              # выдадут организаторы
LLM_TOOLS=auto             # auto | json
LLM_TIMEOUT=30
LLM_FALLBACK_TO_MOCK=true
```

`LLM_PROVIDER=mock` должен работать с первой минуты и до конца хакатона. Это страховка: если ключи задержатся или упадут, разработка и демо не встают.

Если организаторы выдадут GigaChat, авторизация другая: `POST https://ngw.devices.sberbank.ru:9443/api/v2/oauth` с заголовком `Authorization: Basic <ключ>` и полем `scope=GIGACHAT_API_PERS` возвращает токен на 30 минут. Дальше протокол совместим с OpenAI. Реализовать отдельным классом за тем же интерфейсом, ветка по `LLM_PROVIDER`.

### Интерфейс клиента

```python
class LLMClient:
    def complete_json(self, system: str, user: str, schema: dict) -> tuple[dict, int]:
        """Возвращает разобранный объект и время в миллисекундах."""

    def complete_tools(self, system: str, user: str, tools: list[dict]) -> tuple[dict, int]:
        """Возвращает {'name': ..., 'arguments': {...}} и время в миллисекундах."""
```

Требования к реализации:

- таймаут из `LLM_TIMEOUT`, один повтор при сетевой ошибке или коде 5xx;
- `temperature=0.2`, чтобы разборы были воспроизводимы на демо;
- если `LLM_FALLBACK_TO_MOCK=true`, при любой неустранимой ошибке отдавать ответ заглушки и помечать `model="mock"`, не ронять запрос;
- функция `parse_json_loose(text)`: сначала `json.loads`, при неудаче взять подстроку от первой `{` до последней `}`, при повторной неудаче — один дополнительный вызов модели с требованием вернуть только JSON.

### Шаг 1. Системный промпт извлечения структуры

```
Ты — аналитик первой линии технической поддержки крупной компании.
Тебе приходит обращение пользователя: письмо или текстовая расшифровка телефонного разговора.
Твоя задача — разобрать обращение и вернуть строго один JSON-объект по заданной схеме.

Правила.
1. Пиши по-русски, кратко и по делу, без вежливых оборотов и без воды.
2. В summary — одно-два предложения: кто обратился, что не работает, с какого момента.
3. В intents перечисли все отдельные проблемы и вопросы внутри обращения. Если их несколько — не сливай в один.
4. category выбирай строго из списка: access, vpn, network, hardware, software, platform, email, docs, other.
5. priority назначай по правилам:
   P1 — остановлена работа группы людей или сервис недоступен целиком;
   P2 — один человек полностью заблокирован, обходного пути нет;
   P3 — работать можно, есть неудобство или обходной путь;
   P4 — вопрос, консультация, пожелание.
   В priority_reason объясни выбор одной фразой.
6. team выбирай строго из списка: l1_support, access_team, network_team, hardware_team, apps_team, platform_team, security.
7. В entities помещай только то, что реально написано в обращении. Ничего не придумывай и не достраивай.
   Если поля нет в тексте — просто не включай его в объект.
8. В missing_fields перечисли данные, без которых исполнитель не сможет начать работу.
   Для каждого укажи field, why и question — готовый вопрос пользователю на русском, вежливый, одно предложение.
   Если данных достаточно — верни пустой список.
9. confidence — твоя уверенность в разборе от 0 до 1. Ставь ниже 0.6, если обращение путаное или в нём не хватает ключевых данных.
10. Не выдумывай факты. Не добавляй полей сверх схемы. Верни только JSON, без пояснений и без markdown-обёртки.
```

Пользовательское сообщение:

```
Канал: {channel_label}
Тема: {subject}
От: {author_name} <{author_email}>
Получено: {received_at}

Текст обращения:
"""
{body}
"""
```

### Схема ответа шага 1

```json
{
  "type": "object",
  "required": ["summary","intents","category","service","priority","priority_reason",
               "team","entities","missing_fields","sentiment","confidence"],
  "additionalProperties": false,
  "properties": {
    "summary":         { "type": "string" },
    "intents":         { "type": "array", "items": { "type": "string" } },
    "category":        { "type": "string", "enum": ["access","vpn","network","hardware","software","platform","email","docs","other"] },
    "service":         { "type": "string" },
    "priority":        { "type": "string", "enum": ["P1","P2","P3","P4"] },
    "priority_reason": { "type": "string" },
    "team":            { "type": "string", "enum": ["l1_support","access_team","network_team","hardware_team","apps_team","platform_team","security"] },
    "entities":        { "type": "object" },
    "missing_fields":  { "type": "array", "items": {
        "type": "object", "required": ["field","why","question"],
        "properties": { "field": {"type":"string"}, "why": {"type":"string"}, "question": {"type":"string"} } } },
    "sentiment":       { "type": "string", "enum": ["calm","annoyed","angry"] },
    "confidence":      { "type": "number", "minimum": 0, "maximum": 1 }
  }
}
```

### Шаг 2. Обычная программная логика, без LLM

Это место отдельно проговаривается на защите: мы сознательно не тратим модель там, где хватает кода.

**Поиск похожих заявок.** Без эмбеддингов и без внешних библиотек.

1. Нормализовать текст: нижний регистр, выкинуть пунктуацию, разбить по пробелам, отбросить слова короче трёх букв и стоп-слова (`это`, `для`, `или`, `что`, `как`, `при`, `все`, `нет`, `был`, `есть`).
2. Считать меру Жаккара между множеством слов запроса и множеством слов `title + description` заявки.
3. Прибавить `0.15`, если совпала категория, и ещё `0.10`, если совпал сервис.
4. Отсортировать по убыванию, вернуть до 5 штук со `score >= 0.15`.

**Поиск в базе знаний.** Та же мера плюс `0.2` за каждое попадание в `keywords`.

**Признак массового инцидента.** Если среди обращений за последние 6 часов есть три и более с той же парой `category` и `service`, поставить `mass_incident: true`.

### Шаг 3. Выбор и выполнение действия

Три инструмента в формате OpenAI tools.

```json
[
  {
    "type": "function",
    "function": {
      "name": "create_ticket",
      "description": "Создать заявку в системе. Вызывай, когда данных достаточно, чтобы исполнитель начал работу.",
      "parameters": {
        "type": "object",
        "required": ["title","description","category","service","priority","team"],
        "properties": {
          "title":       { "type": "string", "description": "Краткий заголовок до 80 символов" },
          "description": { "type": "string", "description": "Что произошло, что уже известно, что проверить исполнителю" },
          "category":    { "type": "string", "enum": ["access","vpn","network","hardware","software","platform","email","docs","other"] },
          "service":     { "type": "string" },
          "priority":    { "type": "string", "enum": ["P1","P2","P3","P4"] },
          "team":        { "type": "string", "enum": ["l1_support","access_team","network_team","hardware_team","apps_team","platform_team","security"] }
        }
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "ask_clarification",
      "description": "Подготовить письмо пользователю с уточняющими вопросами. Вызывай, когда без ответов нельзя маршрутизировать или решить обращение.",
      "parameters": {
        "type": "object",
        "required": ["subject","body","questions"],
        "properties": {
          "subject":   { "type": "string" },
          "body":      { "type": "string", "description": "Готовое письмо на русском: приветствие, что уже поняли, пронумерованные вопросы, подпись" },
          "questions": { "type": "array", "items": { "type": "string" } }
        }
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "draft_reply",
      "description": "Подготовить черновик ответа пользователю по статье базы знаний. Вызывай, когда решение известно и заявка не нужна.",
      "parameters": {
        "type": "object",
        "required": ["subject","body"],
        "properties": {
          "subject":     { "type": "string" },
          "body":        { "type": "string", "description": "Готовый ответ с пошаговой инструкцией" },
          "kb_used":     { "type": "array", "items": { "type": "integer" }, "description": "id использованных статей" }
        }
      }
    }
  }
]
```

Системный промпт шага 3:

```
Ты — ассистент оператора первой линии поддержки. Разбор обращения уже сделан.
Выбери ровно одно действие и вызови соответствующий инструмент. Текстом не отвечай.

Как выбирать.
- Если список недостающих данных не пуст и без них исполнитель не сможет начать — вызови ask_clarification
  и включи в письмо все вопросы из missing_fields.
- Если среди статей базы знаний есть прямо подходящая и проблема решается самим пользователем
  за несколько шагов — вызови draft_reply и перескажи инструкцию своими словами, по пунктам.
- В остальных случаях вызови create_ticket.
- Если поднят признак массового инцидента, всё равно создавай заявку, но в описании первой строкой
  укажи: «Возможен массовый сбой, есть похожие обращения».

Требования к текстам.
- Пиши по-русски, на «вы», вежливо, без канцелярита и без извинений через слово.
- В описании заявки укажи, что уже известно из обращения, и что стоит проверить исполнителю.
- Не придумывай факты, которых нет в разборе.
- Подпись всегда: «С уважением, служба технической поддержки».
```

Пользовательское сообщение шага 3 — компактный JSON: результат шага 1, список похожих заявок с их решениями, найденные статьи базы знаний, флаг массового инцидента.

**Запасной путь `LLM_TOOLS=json`.** Если модель не поддерживает инструменты, тот же промпт, но вместо tools просим вернуть:

```json
{ "action": "create_ticket", "arguments": { } }
```

Диспетчер на стороне Python одинаковый в обоих случаях.

### Исполнение инструмента

| Инструмент | Что делает бэкенд |
|---|---|
| `create_ticket` | Создаёт запись в `tickets` со статусом `proposed`, `created_by='agent'`, присваивает ключ `SD-{1000+id}` |
| `ask_clarification` | Создаёт запись в `outbox` с `kind='clarification'`, `status='draft'` |
| `draft_reply` | Создаёт запись в `outbox` с `kind='reply'`, `status='draft'` |

После исполнения обращение переходит в `analyzed`, каждый шаг записывается в `agent_steps`.

---

## 6. Режим заглушки

Файл `backend/app/llm/mock_data.py` содержит правила по ключевым словам. Это не «рандом», а осмысленные ответы, на которых можно вести разработку и, в крайнем случае, демо.

| Слова в теле | Категория | Приоритет | Действие |
|---|---|---|---|
| `vpn`, `туннель`, `удалён` | `vpn` | P2 | `create_ticket` |
| `пароль`, `забыл`, `заблокир`, `учётн` | `access` | P2 | `ask_clarification` |
| `wi-fi`, `wifi`, `сеть`, `интернет` | `network` | P1 | `create_ticket` |
| `принтер`, `ноутбук`, `монитор`, `мышь` | `hardware` | P3 | `create_ticket` |
| `почт`, `outlook`, `календар` | `email` | P3 | `draft_reply` |
| ничего не совпало | `other` | P3 | `ask_clarification` |

В режиме заглушки `confidence` всегда `0.5`, а `model` — строка `mock`. Интерфейс обязан показывать это жёлтой плашкой «Работает на заглушке», чтобы никто случайно не показал жюри фальшивый результат как настоящий.
