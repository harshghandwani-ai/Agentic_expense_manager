"""
app.py — FastAPI application entry point.

Run with:
    uvicorn app:app --reload
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from db import init_db
from ocr import get_engine
from routers import expenses
from routers import chat
from routers import auth
from routers import voice

# ── Logging ───────────────────────────────────────────────────────────────────
# uvicorn sets up its own root logging handler — we attach our loggers to it
# by setting their level. basicConfig() won't work here (uvicorn sets it first).
_LOG_MODULES = ["routers.chat", "routers.expenses", "llm_extractor", "ocr", "__main__"]
for _m in _LOG_MODULES:
    logging.getLogger(_m).setLevel(logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise DB and pre-warm OCR engine on startup."""
    init_db()
    logger.info("[STARTUP] Pre-warming OCR engine...")
    try:
        get_engine()  # loads PaddleOCR model into memory once
        logger.info("[STARTUP] OCR engine ready.")
    except Exception as exc:
        logger.warning("[STARTUP] OCR pre-warm failed (non-fatal): %s", exc)
    yield


app = FastAPI(
    title="Expense Logger API",
    description=(
        "LLM-powered expense tracker. "
        "Log expenses in natural language and query your spending history."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS — allow all origins for local dev; restrict in production ────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(expenses.router, prefix="/api/expenses", tags=["Expenses"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(voice.router, prefix="/api/voice", tags=["Voice"])


# ── Health & Frontend ─────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health() -> dict:
    return {"status": "ok", "service": "expense-logger-api"}

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
