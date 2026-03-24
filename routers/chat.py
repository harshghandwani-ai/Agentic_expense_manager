"""
routers/chat.py — Unified /api/chat endpoint.

Accepts any natural-language message and routes it to the correct pipeline:
  - log   → extract_expense + insert_expense  → returns saved expense
  - query → Text-to-SQL pipeline              → returns AI answer
  - chat  → direct LLM reply                 → returns AI answer
"""
import json
from datetime import date

from fastapi import APIRouter, HTTPException

from db import insert_expense, run_query
from intent_router import route
from models import Expense
from schemas import ChatRequest, ChatResponse, LogResponse

router = APIRouter()


@router.post(
    "",
    response_model=ChatResponse,
    summary="Unified chat endpoint",
    description=(
        "Send any natural-language message. The server automatically routes it to "
        "log an expense, query spending history, or answer general questions."
    ),
)
async def chat(body: ChatRequest) -> ChatResponse:
    try:
        intent, payload = route(body.message)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Intent routing failed: {exc}") from exc

    # ── LOG ───────────────────────────────────────────────────────────────────
    if intent == "log":
        try:
            expense = Expense(**payload)
            row_id = insert_expense(expense)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Expense logging failed: {exc}") from exc

        rows = run_query("SELECT * FROM expenses WHERE id = ?", (row_id,))
        saved = LogResponse(**rows[0]) if rows else None

        fields = expense.model_dump()
        answer = (
            f"Logged expense #{row_id}: {fields['description']} — "
            f"₹{fields['amount']} ({fields['category']}) on {fields['date']} via {fields['payment_mode']}."
        )
        return ChatResponse(intent="log", answer=answer, expense=saved)

    # ── QUERY or CHAT ─────────────────────────────────────────────────────────
    return ChatResponse(intent=intent, answer=payload, expense=None)
