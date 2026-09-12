# Разработчик A — бэкенд, LLM и агент

Ты отвечаешь за всё, что лежит в папке `backend/`. Файлы из `frontend/` не трогаешь никогда.
Перед стартом прочитай `docs/01_CONTRACT.md` целиком. Он — закон.

## Как работать с Claude Code

Запусти Claude в корне проекта. Перед каждым блоком задач давай ему контекст одной командой:

```
Прочитай docs/01_CONTRACT.md полностью. Это контракт проекта, отступать от него нельзя.
Я разработчик бэкенда, работаю только в папке backend/. Папку frontend/ не трогай.
```

Дальше копируй промпты ниже по одному. Не давай два промпта сразу: проверяй результат после каждого.
После каждого выполненного блока — `git add -A && git commit -m "..."`.

---

## Структура папки

```
backend/
  app/
    main.py            FastAPI, CORS, подключение роутеров
    db.py              движок SQLAlchemy, сессия, create_all
    models.py          модели таблиц
    schemas.py         модели Pydantic для запросов и ответов
    dictionaries.py    справочники категорий, приоритетов, команд, действий
    seed.py            загрузка data/*.json в базу
    routers/
      messages.py      /api/messages, /analyze, /apply
      tickets.py       /api/tickets
      misc.py          /api/health, /api/dictionaries, /api/similar, /api/kb, /api/stats, /api/seed
    llm/
      client.py        LLMClient, выбор провайдера, parse_json_loose
      openai_client.py OpenAI-совместимый провайдер
      mock_client.py   заглушка
      mock_data.py     правила заглушки по ключевым словам
      prompts.py       системные промпты и схемы, тексты из контракта
    agent/
      runner.py        оркестратор: шаг 1, шаг 2, шаг 3, запись трассы
      tools.py         определения инструментов и их исполнение
      search.py        поиск похожих заявок и статей, признак массового инцидента
  requirements.txt
  .env.example
```

---

## Такт 1 (10:40–11:40). Каркас и данные

Цель к чекпоинту 1: сервер поднимается, база заполнена, список обращений отдаётся.

### Промпт A1

```
Создай бэкенд-каркас в папке backend/ по структуре из docs/01_CONTRACT.md.

1. requirements.txt: fastapi, uvicorn[standard], sqlalchemy, pydantic, pydantic-settings,
   python-dotenv, httpx. Версии не пинуй.
2. app/db.py: движок SQLAlchemy 2.0 на SQLite по пути backend/supportpilot.db,
   SessionLocal, Base, зависимость get_db для FastAPI.
3. app/models.py: модели messages, analyses, tickets, kb_articles, agent_steps, outbox
   строго по разделу 2 контракта. Поля, помеченные JSON, храни как Text
   и заведи для каждого свойство-хелпер, которое сериализует и разбирает JSON.
   Все даты храни строками ISO 8601.
4. app/dictionaries.py: словари CATEGORIES, PRIORITIES, TEAMS, ACTIONS
   в виде списков {"code": ..., "label": ...} ровно по разделу 1 контракта.
5. app/schemas.py: pydantic-модели MessageOut, MessageListItem, AnalysisOut, TicketOut,
   AgentStepOut, OutboxOut, MessageDetailOut, AnalyzeResponse, ApplyRequest, CreateMessageRequest.
   Формы полей возьми из раздела 4 контракта, не отходи от имён ни на букву.
6. app/main.py: приложение FastAPI с CORS на http://localhost:5173,
   создание таблиц при старте, подключение роутеров, JSON-ответы с ensure_ascii=False.
7. app/routers/misc.py: пока только GET /api/health и GET /api/dictionaries.

Проверь, что `uvicorn app.main:app --reload` из папки backend запускается без ошибок.
```

### Промпт A2

```
Реализуй загрузку демо-данных.

1. app/seed.py: функция seed_database(db, wipe=True). Она стирает все таблицы,
   читает data/seed_messages.json и data/kb_articles.json из корня репозитория
   и заполняет messages и kb_articles.
2. Файл data/seed_messages.json имеет два ключа верхнего уровня:
   "messages" — 12 входящих обращений, "closed_tickets" — 8 уже решённых заявок
   с заполненным полем resolution. Заявки клади в tickets со статусом closed
   и created_by='operator'. Они нужны, чтобы поиску похожих было что находить,
   а их поле resolution — самое ценное, что агент покажет оператору.
   В closed_tickets поле key уже задано, используй его как есть.
   Новые заявки от агента нумеруй, продолжая с SD-1009.
3. Добавь POST /api/seed в misc.py, который вызывает seed_database и возвращает
   {"messages": N, "kb_articles": N, "tickets": N}.
4. Сделай так, чтобы при старте приложения база заполнялась автоматически,
   если таблица messages пуста.

Запусти сервер и проверь curl-ом, что POST /api/seed возвращает 12 обращений.
```

### Промпт A3

```
Реализуй роутер обращений в app/routers/messages.py по разделу 4 контракта:
GET /api/messages с параметрами status, q, limit;
GET /api/messages/{id} с вложенными analysis, steps, tickets, outbox;
POST /api/messages для ручного создания.

В GET /api/messages поле preview — первые 160 символов body с добавлением многоточия,
поля category и priority берутся из последнего разбора или null, если разбора нет.
Сортировка по received_at по убыванию.

Проверь все три эндпоинта через curl и покажи мне ответы.
```

**Готовность к 11:40:** `curl localhost:8000/api/messages` возвращает 12 записей. Скажи об этом разработчику B, он в этот момент переключит один экран с мока на живые данные и это будет хорошо смотреться на чекпоинте.

---

## Такт 2 (11:40–12:40). Живой вызов LLM

Цель к чекпоинту 2: `POST /api/messages/1/analyze` возвращает заполненную структуру.

### Промпт A4

```
Реализуй слой работы с языковой моделью в app/llm/ по разделу 5 контракта.

1. app/llm/prompts.py: константы SYSTEM_EXTRACT, USER_EXTRACT_TEMPLATE, EXTRACT_SCHEMA,
   SYSTEM_DECIDE, TOOLS. Тексты возьми из контракта дословно, ничего не сокращай.
2. app/llm/client.py: базовый класс LLMClient с методами complete_json и complete_tools,
   функция parse_json_loose(text) и фабрика get_llm_client(), которая выбирает провайдера
   по переменной окружения LLM_PROVIDER.
3. app/llm/openai_client.py: провайдер поверх httpx, POST {LLM_BASE_URL}/chat/completions,
   заголовок Authorization: Bearer {LLM_API_KEY}, temperature 0.2, таймаут LLM_TIMEOUT,
   один повтор при сетевой ошибке или коде 5xx.
   В complete_json проси response_format={"type":"json_object"} и дополнительно
   вставляй схему в системное сообщение текстом, потому что не все эндпоинты поддерживают
   строгие схемы. Результат прогоняй через parse_json_loose.
   В complete_tools передавай tools и tool_choice="required",
   возвращай {"name": ..., "arguments": {...}} из первого tool_call.
4. app/llm/mock_data.py и app/llm/mock_client.py: заглушка по таблице из раздела 6 контракта.
   Заглушка обязана возвращать ответ той же формы, что и живая модель.
5. Если LLM_FALLBACK_TO_MOCK=true, любая неустранимая ошибка живого провайдера
   приводит к ответу заглушки, а не к исключению. Поле model в этом случае — строка "mock".
6. Создай backend/.env.example со всеми переменными из контракта.
   Добавь backend/.env в .gitignore.

Измеряй время каждого вызова и возвращай его вторым элементом кортежа.
```

### Промпт A5

```
Реализуй первый шаг агента.

1. app/agent/runner.py: функция run_analysis(db, message, force=False).
   Пока в ней только шаг 1: вызов complete_json с SYSTEM_EXTRACT и заполненным
   USER_EXTRACT_TEMPLATE, валидация результата по EXTRACT_SCHEMA.
2. Валидируй руками, без jsonschema: проверь, что category, priority, team, sentiment
   входят в справочники, confidence в диапазоне от 0 до 1, intents и missing_fields — списки.
   Если поле некорректно, подставь безопасное значение: category='other', priority='P3',
   team='l1_support', и понизь confidence до 0.4.
3. Сохрани результат в таблицу analyses, запиши шаг в agent_steps
   с kind='llm', name='extract_structure'.
4. Добавь POST /api/messages/{id}/analyze в messages.py.
   Без параметра force=true повторный вызов отдаёт сохранённый разбор и не дёргает модель.
5. Ответ собирай в форме AnalyzeResponse из контракта: analysis, steps, tickets, outbox.
   Пока tickets и outbox всегда пустые списки.

Проверь curl-ом при LLM_PROVIDER=mock, потом с живым ключом, если он уже есть.
```

**К 12:30 отправить организаторам ссылку на репозиторий.** Это делает третий участник, но напомни ему.

---

## Такт 3 (12:40–14:40). Агент, инструменты, действия

Это главный такт. Здесь появляется всё, за что ставят баллы.

### Промпт A6

```
Реализуй поиск без языковой модели в app/agent/search.py по разделу 5 контракта, шаг 2.

1. normalize(text) -> set[str]: нижний регистр, убрать пунктуацию, разбить по пробелам,
   отбросить слова короче трёх символов и стоп-слова это для или что как при все нет был есть.
2. jaccard(a, b) -> float.
3. search_similar_tickets(db, query_text, category, service, limit=5) -> list[dict]
   по правилам контракта: мера Жаккара по title и description, плюс 0.15 за совпадение
   категории, плюс 0.10 за совпадение сервиса, порог 0.15, сортировка по убыванию.
   Возвращай id, key, title, status, resolution, score с округлением до двух знаков.
4. search_kb(db, query_text, category, limit=3) -> list[dict]: та же мера
   плюс 0.2 за каждое попадание в keywords. Возвращай id, title, category, excerpt, score.
5. detect_mass_incident(db, category, service, hours=6, threshold=3) -> bool.
6. Добавь GET /api/similar и GET /api/kb в misc.py.

Не подключай сюда никакие внешние библиотеки, только стандартная библиотека Python.
```

### Промпт A7

```
Реализуй инструменты агента в app/agent/tools.py.

1. TOOLS уже лежит в prompts.py. Здесь напиши исполнители:
   execute_create_ticket(db, message, analysis, args) -> Ticket
     создаёт заявку со статусом proposed, created_by='agent',
     key вида SD-{1000+id}, переносит entities из разбора;
   execute_ask_clarification(db, message, analysis, args) -> Outbox
     создаёт запись outbox с kind='clarification', status='draft';
   execute_draft_reply(db, message, analysis, args) -> Outbox
     создаёт запись outbox с kind='reply', status='draft'.
2. Диспетчер execute_tool(db, message, analysis, name, args), который по имени
   вызывает нужный исполнитель и возвращает кортеж (объект, короткая строка для трассы).
   Для заявки строка — её ключ, для письма — тема.
3. Каждый исполнитель валидирует аргументы: недостающие поля заполняет из analysis,
   значения вне справочников заменяет на безопасные. Исключений наружу не бросай.
```

### Промпт A8

```
Доделай оркестратор в app/agent/runner.py до полного прогона.

Последовательность внутри run_analysis:
  шаг 1  llm  extract_structure          уже есть
  шаг 2  tool search_similar_tickets     search.py, записать в трассу
  шаг 3  tool search_knowledge_base      search.py, записать в трассу
  шаг 4  llm  decide_action              complete_tools с SYSTEM_DECIDE и TOOLS
  шаг 5  tool <имя выбранного инструмента>  execute_tool, записать в трассу

Пользовательское сообщение шага 4 — компактный JSON: результат шага 1,
список похожих заявок вместе с их полем resolution, найденные статьи базы знаний,
флаг mass_incident. Вот тут важно: именно решения похожих заявок дают модели контекст,
не выбрасывай их.

Если переменная LLM_TOOLS равна json, вместо complete_tools используй complete_json
со схемой {"action": ..., "arguments": {...}} и тем же системным промптом,
дополненным требованием вернуть JSON. Дальше логика одинаковая.

После выбора действия обнови запись analyses: suggested_action, action_reason,
similar_ticket_ids, kb_article_ids, mass_incident, latency_ms как сумма всех шагов, model.
Переведи message.status в 'analyzed'.
Верни AnalyzeResponse со всеми созданными заявками и письмами.

Оберни весь прогон в try: если что-то падает, всё равно верни разбор шага 1
с suggested_action='ask_clarification' и записанной ошибкой в трассе.
Демо не должно падать никогда.
```

### Промпт A9

```
Реализуй POST /api/messages/{id}/apply по разделу 4 контракта.

decision confirm: заявка proposed -> open, записи outbox draft -> sent,
  обращение -> processed.
decision edit: сначала применить overrides к заявке и edited_body к письму,
  затем то же, что при confirm.
decision reject: заявка -> rejected, обращение возвращается в new.

Поля в overrides, которые не входят в справочники, игнорируй молча.
Ответ — та же структура, что у GET /api/messages/{id}.

Ещё добавь PATCH /api/tickets/{id} и GET /api/tickets с фильтрами
status, category, priority, q.
```

**К 14:00 договориться с разработчиком B о переключении фронта на живой бэкенд.** Дальше он ловит настоящие ошибки, а не мокнутые.

---

## Такт 4 (14:40–17:00). Статистика и надёжность

### Промпт A10

```
Реализуй GET /api/stats по разделу 4 контракта.
Все агрегаты считай запросами к базе, подписи категорий и приоритетов
подставляй из dictionaries.py.
mass_incidents: сгруппируй обращения за последние 6 часов по паре category и service,
оставь группы от трёх штук, для каждой собери message_ids и составь текст hint
на русском вида «Три обращения по Wi-Fi за два часа, возможен массовый сбой».
```

### Промпт A11

```
Приведи бэкенд в порядок перед сдачей.

1. Пройдись по всем эндпоинтам и убедись, что ни один не может вернуть 500
   при пустой базе, отсутствующем ключе LLM и несуществующем id.
2. GET /api/health должен честно показывать состояние модели:
   live, mock или error, плюс имя модели и число обращений в базе.
3. Напиши backend/README.md: требования, установка, .env, запуск, список эндпоинтов
   с примерами curl. Коротко, на русском.
4. Проверь сценарий с нуля: удалить supportpilot.db, запустить сервер,
   разобрать три разных обращения, подтвердить одно, отклонить одно.
   Покажи мне вывод.
```

---

## Что проверить перед сдачей

- [ ] `POST /api/seed` возвращает базу в исходное состояние за секунду.
- [ ] Разбор обращения про VPN даёт `create_ticket`, и заявка появляется в `/api/tickets`.
- [ ] Разбор обращения без логина даёт `ask_clarification` с конкретными вопросами.
- [ ] Разбор про три обращения по Wi-Fi поднимает `mass_incident`.
- [ ] При `LLM_PROVIDER=mock` работает весь сценарий целиком.
- [ ] При неверном `LLM_API_KEY` сервер не падает, `/api/health` показывает `error` или `mock`.
- [ ] `backend/.env` не попал в git.
