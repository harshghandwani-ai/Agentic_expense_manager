"""
app.py — FastAPI application entry point.

Run with:
    uvicorn app:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from db import init_db
from routers import expenses
from routers import chat
from routers import auth
from routers import voice


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the database on startup."""
    init_db()
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
