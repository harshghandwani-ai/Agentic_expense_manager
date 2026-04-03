"""
routers/chat.py -- Unified /api/chat endpoint.

Accepts any natural-language message and routes it to the correct pipeline:
  - log   -> LLM extracts expense fields, returns ExpensePreview (NOT saved yet)
             The frontend must call POST /api/expenses/confirm to save.
  - query -> Text-to-SQL pipeline -> returns AI answer
  - chat  -> direct LLM reply    -> returns AI answer
"""
from fastapi import APIRouter, Depends, HTTPException

from auth_utils import TokenData, get_current_user
from db import get_chat_history, insert_chat_message, upsert_budget
from intent_router import route
from query_engine import execute_read_expenses, summarize_results
from schemas import ChatRequest, ChatResponse, ExpensePreview

router = APIRouter()


@router.post(
    "",
    response_model=ChatResponse,
    summary="Unified chat endpoint",
    description=(
        "Send any natural-language message. The server routes it to "
        "log an expense (returns preview for confirmation), "
        "query spending history, or answer general questions."
    ),
)
async def chat(
    body: ChatRequest,
    current_user: TokenData = Depends(get_current_user),
) -> ChatResponse:
    # 1. Fetch history (capped at 6 messages / 3 turns)
    history = get_chat_history(current_user.user_id, limit=8)
    
    try:
        # 2. Pass history to router
        intent, payload = route(body.message, history=history)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Intent routing failed: {exc}") from exc

    # ---- LOG: extract fields, return preview -- do NOT save to DB -----------
    if intent == "log":
        try:
            preview = ExpensePreview(
                amount=payload["amount"],
                category=payload["category"],
                date=payload["date"],
                payment_mode=payload["payment_mode"],
                description=payload["description"],
                type=payload.get("type", "expense"),
                ocr_text=None,
                source="text",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Could not build expense preview from extracted data: {exc}",
            ) from exc

        answer = (
            f"Here's what I extracted from your message. "
            f"Please review the details below and confirm (or edit) before saving."
        )
        return ChatResponse(intent="log", answer=answer, expense=preview)

    # ---- QUERY --------------------------------------------------------------
    if intent == "query":
        try:
            tool_result = execute_read_expenses(payload, user_id=current_user.user_id)
            answer = summarize_results(body.message, tool_result)
            return ChatResponse(intent="query", answer=answer, expense=None)
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"Failed to query expenses: {exc}"
            ) from exc

    # ---- BUDGET -------------------------------------------------------------
    if intent == "budget":
        try:
            amount = payload.get("amount")
            category = payload.get("category", "total")
            period = payload.get("period", "monthly")
            
            if not amount:
                 raise HTTPException(status_code=400, detail="Budget amount is required.")
            
            upsert_budget(current_user.user_id, category, amount, period)
            
            # Save message turn
            insert_chat_message(current_user.user_id, "user", body.message)
            answer = f"Done! I've set your {period} budget for **{category}** to **\u20b9{amount:,.2f}**. I'll help you track it in the Stats tab."
            insert_chat_message(current_user.user_id, "assistant", answer)
            
            return ChatResponse(intent="budget", answer=answer, expense=None)
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"Failed to set budget: {exc}"
            ) from exc

    # ---- CHAT ---------------------------------------------------------------
    # Save the conversation turn to the database
    insert_chat_message(current_user.user_id, "user", body.message)
    insert_chat_message(current_user.user_id, "assistant", payload)
    
    return ChatResponse(intent=intent, answer=payload, expense=None)
