"""
routers/chat.py -- Unified /api/chat endpoint.

Accepts any natural-language message and routes it to the correct pipeline:
  - log   -> LLM extracts expense fields, returns ExpensePreview (NOT saved yet)
             The frontend must call POST /api/expenses/confirm to save.
  - query -> Text-to-SQL pipeline -> returns AI answer
  - chat  -> direct LLM reply    -> returns AI answer
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import json
import time
import uuid
import logging
import asyncio

from auth_utils import TokenData, get_current_user
from db import get_chat_history, insert_chat_message, upsert_budget
from intent_router import route, client, ROUTER_SYSTEM_PROMPT
from config import OPENAI_MODEL
from query_engine import execute_read_expenses, summarize_results
from schemas import ChatRequest, ChatResponse, ExpensePreview
from db import clear_chat_history

router = APIRouter()
logger = logging.getLogger(__name__)

@router.delete("")
async def clear_chat(current_user: TokenData = Depends(get_current_user)):
    clear_chat_history(current_user.user_id)
    return {"status": "cleared"}


@router.post(
    "",
    summary="Unified streaming chat endpoint",
)
async def chat(
    body: ChatRequest,
    current_user: TokenData = Depends(get_current_user),
):
    async def event_generator():
        request_id = str(uuid.uuid4())[:8]
        t_request_start = time.time()

        # 1. Fetch history (capped at 8 messages / 4 turns)
        history = get_chat_history(current_user.user_id, limit=8)
        
        # Insert user message for context immediately
        insert_chat_message(current_user.user_id, "user", body.message)
        
        try:
            # 2. Intent Classification
            t_intent = time.time()
            intent, payload = route(body.message, history=history)
            logger.info(
                "[LATENCY] request_id=%s stage=intent_classification intent=%s duration_ms=%d",
                request_id, intent, round((time.time() - t_intent) * 1000)
            )
            
            # Send the detected intent first
            yield f"data: {json.dumps({'type': 'intent', 'value': intent})}\n\n"
            await asyncio.sleep(0.01)

            # ---- LOG --------------------------------------------------------
            if intent == "log":
                t_extract = time.time()
                preview = {
                    "amount": payload["amount"],
                    "category": payload["category"],
                    "date": payload["date"],
                    "payment_mode": payload["payment_mode"],
                    "description": payload["description"],
                    "type": payload.get("type", "expense"),
                    "source": "text"
                }
                logger.info(
                    "[LATENCY] request_id=%s stage=log_preview duration_ms=%d",
                    request_id, round((time.time() - t_extract) * 1000)
                )
                answer = "Here's what I extracted. Please confirm or edit before saving."
                yield f"data: {json.dumps({'type': 'log', 'answer': answer, 'expense': preview})}\n\n"

            # ---- QUERY ------------------------------------------------------
            elif intent == "query":
                t_query = time.time()
                tool_result = execute_read_expenses(payload, history=history, user_id=current_user.user_id)
                
                # Start streaming the response
                completion = summarize_results(body.message, tool_result, history=history)
                full_content = ""
                for chunk in completion:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_content += content
                        yield f"data: {json.dumps({'type': 'chunk', 'value': content})}\n\n"
                        await asyncio.sleep(0.01)

                logger.info(
                    "[LATENCY] request_id=%s stage=query_execution duration_ms=%d",
                    request_id, round((time.time() - t_query) * 1000)
                )
                insert_chat_message(current_user.user_id, "assistant", full_content)
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

            # ---- BUDGET -----------------------------------------------------
            elif intent == "budget":
                amount = payload.get("amount")
                category = payload.get("category", "total")
                period = payload.get("period", "monthly")
                
                if amount:
                    upsert_budget(current_user.user_id, category, amount, period)
                    answer = f"Done! I've set your {period} budget for **{category}** to **\u20b9{amount:,.2f}**."
                    insert_chat_message(current_user.user_id, "assistant", answer)
                    yield f"data: {json.dumps({'type': 'budget', 'answer': answer})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Budget amount missing'})}\n\n"

            # ---- CHAT -------------------------------------------------------
            else:
                # Start streaming reply
                messages = [{"role": "system", "content": ROUTER_SYSTEM_PROMPT}]
                if history: messages.extend(history)
                messages.append({"role": "user", "content": body.message})
                
                full_content = ""
                first_token = True
                t_stream_start = time.time()
                completion = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=messages,
                    stream=True,
                    temperature=0.7
                )
                
                for chunk in completion:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        if first_token:
                            logger.info(
                                "[LATENCY] request_id=%s stage=chat_ttft duration_ms=%d",
                                request_id, round((time.time() - t_stream_start) * 1000)
                            )
                            first_token = False
                        full_content += content
                        yield f"data: {json.dumps({'type': 'chunk', 'value': content})}\n\n"
                        await asyncio.sleep(0.01)
                
                # Save assistant message
                insert_chat_message(current_user.user_id, "assistant", full_content)
                logger.info(
                    "[LATENCY] request_id=%s stage=chat_stream_complete duration_ms=%d",
                    request_id, round((time.time() - t_stream_start) * 1000)
                )
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        finally:
            logger.info(
                "[LATENCY] request_id=%s stage=request_total duration_ms=%d",
                request_id, round((time.time() - t_request_start) * 1000)
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")
