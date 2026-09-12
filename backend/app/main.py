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

from app.routers import messages, misc  # noqa: E402

app.include_router(misc.router)
app.include_router(messages.router)


@app.get("/")
def root() -> dict:
    return {"service": "SupportPilot", "docs": "/docs", "health": "/api/health"}
