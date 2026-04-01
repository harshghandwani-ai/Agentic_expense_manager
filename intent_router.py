"""
intent_router.py — Classifies user input as LOG, QUERY, or CHAT via OpenAI tool-calling.

Returns a tuple: (intent, payload)
  intent == "query" -> payload is the AI's natural-language answer to a spending question
  intent == "log"   -> payload is the raw user text (caller runs llm_extractor)
  intent == "chat"  -> payload is the AI's direct conversational reply

"""
import json
from datetime import date
from typing import Any
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

TODAY = date.today().isoformat()



QUERY_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "read_expenses",
        "description": (
            "Query the local expenses SQLite database. "
            "Use this whenever the user asks about their spending, "
            "totals, categories, payment modes, or history."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The user's natural-language question about their expenses.",
                }
            },
            "required": ["query"],
        },
    },
}

LOG_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "log_expense",
        "description": "Log a new expense into the database. Use this when the user describes spending money.",
        "parameters": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "The monetary amount spent (float)."},
                "category": {"type": "string", "enum": ["food", "shopping", "transport", "entertainment", "health", "utilities", "other"], "description": "The category of the expense."},
                "date": {"type": "string", "description": "The date in YYYY-MM-DD format. Use today if not specified."},
                "payment_mode": {"type": "string", "description": "The payment mode. Default to 'cash' if not mentioned."},
                "description": {"type": "string", "description": "A brief noun phrase describing what was bought."}
            },
            "required": ["amount", "category", "date", "payment_mode", "description"]
        }
    }
}

ROUTER_SYSTEM_PROMPT = f"""
You are a helpful personal expense assistant. Today is {TODAY}.

The user's message falls into exactly one of three categories:

1. LOG - The user is describing a new expense they want to record.
Examples: "I spent 500 on shoes using UPI", "paid 200 for coffee"
-> Call the log_expense tool.

2. QUERY - The user is asking a question about their past spending/expenses in the database.
Examples: "how much did I spend this month", "show my last 5 expenses", "what category do I spend most on"
-> Call the read_expenses tool.

3. CHAT - Anything else: greetings, general questions, clarifications, meta questions about the conversation.
Examples: "what was my last query", "hello", "what can you do", "what did I just say"
-> Reply conversationally and helpfully. Do NOT call either tool.

Be precise about which category applies. When in doubt between LOG and CHAT, ask yourself:
is there a clear monetary amount being spent. If not, it is CHAT.
"""


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

    # First LLM call — may or may not invoke the tool
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        tools=[QUERY_TOOL_DEFINITION, LOG_TOOL_DEFINITION],
        tool_choice="auto",
        temperature=0,
    )

    choice = response.choices[0]

    # ---- Tool call path: user asked about spending history or wanted to log ----
    if choice.finish_reason == "tool_calls":
        tool_call = choice.message.tool_calls[0]
        args = json.loads(tool_call.function.arguments)

        if tool_call.function.name == "log_expense":
            return ("log", args)

        elif tool_call.function.name == "read_expenses":
            query_text = args.get("query", user_input)
            return ("query", query_text)

    # ---- No tool call: fallback to chat response ----
    reply = choice.message.content.strip() if choice.message.content else ""

    return ("chat", reply)