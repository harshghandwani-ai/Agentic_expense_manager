"""
intent_router.py — Classifies user input as LOG, QUERY, or CHAT via OpenAI tool-calling.

Returns a tuple: (intent, payload)
  intent == "query" -> payload is the AI's natural-language answer to a spending question
  intent == "log"   -> payload is the raw user text (caller runs llm_extractor)
  intent == "chat"  -> payload is the AI's direct conversational reply

"""
import json
from datetime import date
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

TODAY = date.today().isoformat()

class LogExpenseArgs(BaseModel):
    amount: float = Field(description="The monetary amount (float).")
    category: Literal["food", "shopping", "transport", "entertainment", "health", "utilities", "salary", "gift", "investment", "other"] = Field(description="The category of the transaction.")
    date: str = Field(description="The date in YYYY-MM-DD format. Use today if not specified.")
    payment_mode: str = Field(description="The payment mode: cash, UPI, bank transfer, etc.")
    description: str = Field(description="A brief noun phrase describing the transaction.")
    type: Literal["expense", "income"] = Field(description="Whether this is an 'expense' (spending) or 'income' (receiving).")

class ReadExpensesArgs(BaseModel):
    query: str = Field(description="The user's question, fully rewritten to be self-contained using chat history context.")

class SetBudgetArgs(BaseModel):
    amount: float = Field(description="The budget amount (float).")
    category: Literal["food", "shopping", "transport", "entertainment", "health", "utilities", "salary", "gift", "investment", "other", "total"] = Field(description="The category. Use 'total' for an overall budget.")
    period: Literal["monthly", "weekly"] = Field(description="The budget period. Default is 'monthly'.")

class RouteDecision(BaseModel):
    reasoning: str = Field(description="Analyze chat history and current message step-by-step. What is the user trying to do? Are they asking a follow-up?")
    intent: Literal["log", "query", "budget", "chat"]
    log_args: Optional[LogExpenseArgs] = Field(None, description="Provide if intent is 'log'")
    query_args: Optional[ReadExpensesArgs] = Field(None, description="Provide if intent is 'query'")
    budget_args: Optional[SetBudgetArgs] = Field(None, description="Provide if intent is 'budget'")
    chat_response: Optional[str] = Field(None, description="The conversational reply if intent is 'chat'.")

ROUTER_SYSTEM_PROMPT = f"""You are PennyWise AI, a concise, engaging personal finance assistant. Today: {TODAY}.

SCOPE: Help users log transactions, query spending history, and set budgets. Politely decline non-finance topics.

ROUTING & FORMATTING —
1. Money exchanged (spent/received) → call log_expense (type='income' for received).
2. Question about past spending/history (including follow-ups like 'when was that?') → call read_expenses. Make 'query' fully self-contained using chat history.
3. Setting/updating a budget → call set_budget (use 'total' if no category).
4. Direct conversational reply (chat) → Use engaging Markdown (bullet points, *italics*), bold important keywords, and sprinkle 1-2 fun emojis.

Keep responses brief, lively, and highly readable."""


def route(user_input: str, history: list[dict] = None) -> tuple[str, Any]:
    """
    Route user input to LOG, QUERY, or CHAT pipeline.

    Returns:
      ("query", answer_text)  -- AI answered a spending question using the DB
      ("log",   expense_dict) -- AI extracted expense and caller should insert it
      ("chat",  answer_text)  -- AI answered a general/conversational question
    """

    messages = [{"role": "system", "content": ROUTER_SYSTEM_PROMPT}]
    
    # Prepend history if available
    if history:
        messages.extend(history)
        
    # Append the current user message
    messages.append({"role": "user", "content": user_input})

    response = client.beta.chat.completions.parse(
        model=OPENAI_MODEL,
        messages=messages,
        response_format=RouteDecision,
        temperature=0,
    )

    decision: RouteDecision = response.choices[0].message.parsed

    print(f"[ROUTER] Intent: {decision.intent} | Reasoning: {decision.reasoning}")

    if decision.intent == "log":
        return ("log", decision.log_args.model_dump() if decision.log_args else {})
    elif decision.intent == "query":
        query_text = decision.query_args.query if decision.query_args else user_input
        return ("query", query_text)
    elif decision.intent == "budget":
        return ("budget", decision.budget_args.model_dump() if decision.budget_args else {})
    else:
        return ("chat", decision.chat_response or "")