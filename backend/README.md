# SaluteAgent — бэкенд

FastAPI и SQLite. Разбирает обращения через языковую модель, ищет похожие заявки
и сам выполняет действие: создаёт заявку, готовит уточнение или черновик ответа.

## Запуск

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Откроется на `http://localhost:8000`, интерактивная документация на `/docs`.
База создаётся сама и при первом запуске заполняется демо-данными из `../data/`.

## Настройки

Все в `backend/.env`, пример в `.env.example`.

| Переменная | Назначение |
|---|---|
| `LLM_PROVIDER` | `openai`, `gigachat` или `mock` |
| `LLM_BASE_URL` | Адрес совместимого с OpenAI эндпоинта |
| `LLM_API_KEY` | Ключ от организаторов |
| `LLM_MODEL` | Имя модели |
| `LLM_TOOLS` | `auto` для вызова инструментов, `json` если модель их не умеет |
| `LLM_TIMEOUT` | Таймаут одного обращения, секунды |
| `LLM_FALLBACK_TO_MOCK` | При ошибке модели отдавать ответ заглушки вместо падения |

**Без ключа всё работает.** При `LLM_PROVIDER=mock` включается разбор по ключевым
словам: категория, приоритет, извлечение логина и кода ошибки, выбор действия.
Сценарий проходит целиком, а `/api/health` честно показывает режим `mock`.

## Эндпоинты

```bash
curl localhost:8000/api/health
curl localhost:8000/api/dictionaries
curl "localhost:8000/api/messages?status=new"
curl localhost:8000/api/messages/1
curl -X POST localhost:8000/api/messages/1/analyze
curl -X POST localhost:8000/api/messages/1/analyze?force=true
curl -X POST localhost:8000/api/messages/1/apply \
  -H 'Content-Type: application/json' \
  -d '{"decision":"edit","overrides":{"priority":"P1"}}'
curl "localhost:8000/api/tickets?priority=P1"
curl -X PATCH localhost:8000/api/tickets/9 \
  -H 'Content-Type: application/json' -d '{"status":"closed"}'
curl "localhost:8000/api/similar?message_id=1"
curl -G localhost:8000/api/kb --data-urlencode "q=не работает vpn"
curl localhost:8000/api/stats
curl -X POST localhost:8000/api/seed
```

`POST /api/seed` возвращает базу в исходное состояние за секунду. Полезно
непосредственно перед защитой.

## Как устроен прогон агента

```
1. Модель   extract_structure        свободный текст -> структура
2. Код      search_similar_tickets   похожие закрытые заявки и их решения
3. Код      search_knowledge_base    подходящие статьи
4. Модель   decide_action            выбор инструмента и его аргументов
5. Код      create_ticket            реальное исполнение инструмента
   либо     ask_clarification
   либо     draft_reply
```

Модель работает на двух шагах из пяти. Поиск, подсчёт повторов и запись в базу —
обычный код: это быстрее, дешевле и даёт один и тот же результат при каждом запуске.

Заявка создаётся сразу, но со статусом `proposed`. В `open` она переходит только
после подтверждения оператором через `/apply`. Письма никуда не уходят сами.

## Где что лежит

| Файл | Отвечает за |
|---|---|
| `app/llm/prompts.py` | Системные промпты. Константа `MINDSET` задаёт стиль мышления помощника и подставляется в оба промпта |
| `app/agent/runner.py` | Оркестратор пяти шагов и запись трассы |
| `app/agent/tools.py` | Исполнение инструментов |
| `app/agent/search.py` | Поиск похожих и признак массового сбоя |
| `app/llm/mock_data.py` | Правила заглушки по ключевым словам |
| `app/dictionaries.py` | Категории, приоритеты, команды, статусы |

## Признак массового сбоя

Поднимается, когда за последние 6 часов пришло три и более обращения одной
категории по одному сервису. Считается только для категорий, где сервис общий
для многих людей: сеть, VPN, платформы, почта, доступы. Сломанный ноутбук
у одного сотрудника и принтер у другого общим инцидентом не считаются.
