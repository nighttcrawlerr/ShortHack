"""Точка входа приложения SupportPilot."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import SessionLocal, create_all


class UTF8JSONResponse(JSONResponse):
    """Русский текст в ответах должен быть читаемым, а не последовательностью \\uXXXX."""

    def render(self, content) -> bytes:
        import json

        return json.dumps(
            content, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_all()
    db = SessionLocal()
    try:
        from app.seed import seed_if_empty

        seed_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="SupportPilot API",
    version="0.1.0",
    description="ИИ-помощник первой линии технической поддержки",
    default_response_class=UTF8JSONResponse,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import messages, misc, tickets  # noqa: E402

app.include_router(misc.router)
app.include_router(messages.router)
app.include_router(tickets.router)


# --- отдача собранного интерфейса ------------------------------------------
#
# В разработке фронтенд живёт на своём порту под Vite. В развёрнутом виде
# собранные файлы лежат рядом, и приложение становится одним процессом
# на одном порту: так его проще поднимать и не нужен отдельный веб-сервер.

from pathlib import Path  # noqa: E402

from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if (DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon() -> FileResponse:
        return FileResponse(DIST / "favicon.svg")

    @app.get("/", include_in_schema=False)
    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str = "") -> FileResponse:
        """Любой неизвестный путь отдаёт страницу приложения.

        Маршруты API объявлены выше и перехватываются раньше, сюда попадают
        только обращения браузера за самой страницей.
        """
        candidate = DIST / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")

else:

    @app.get("/")
    def root() -> dict:
        return {
            "service": "SupportPilot",
            "docs": "/docs",
            "health": "/api/health",
            "note": "Интерфейс не собран. Запустите npm run build в папке frontend",
        }
