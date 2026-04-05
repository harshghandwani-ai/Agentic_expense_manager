"""
query_engine.py — Text-to-SQL pipeline for expense queries.

Pipeline:
  1. Generate SQL  (LLM)
  2. Validate SQL  (only SELECTs allowed)
  3. Execute SQL   (SQLite via db.run_query)
  4. Return result (list of dicts or scalar string)
"""
import json
from datetime import date
from openai import OpenAI
from pydantic import BaseModel, Field
from db import run_query
from config import OPENAI_API_KEY, OPENAI_MODEL

class SQLResponse(BaseModel):
    sql: str = Field(description="The raw SQLite SELECT statement without any markdown fences")

client = OpenAI(api_key=OPENAI_API_KEY)

TODAY = date.today().isoformat()

# ─── OpenAI tool definition ───────────────────────────────────────────────────

TOOL_DEFINITION = {
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

# ─── DB schema injected into the prompt ───────────────────────────────────────

DB_SCHEMA = """
Table: expenses
  id           INTEGER PRIMARY KEY
  user_id      INTEGER   -- owner of this row (always filter by current user)
  amount       REAL      -- monetary amount
  category     TEXT      -- category e.g. food, salary, gift, shopping, utilities
  date         TEXT      -- YYYY-MM-DD
  payment_mode TEXT      -- cash, UPI, bank transfer, etc.
  description  TEXT      -- brief summary of transaction
  type         TEXT      -- 'expense' or 'income' (ALWAYS distinguish between them)
  created_at   TEXT      -- ISO-8601 UTC timestamp
"""

SQL_SYSTEM_PROMPT_TEMPLATE = """You are a SQLite expert. Today is {today}.

Given a natural-language question about finances, generate a single valid SQLite SELECT statement.

Database schema:
{schema}

Rules:
- Output ONLY the raw SQL. No markdown fences, no explanation.
- Use only SELECT statements.
- ALWAYS include the condition: user_id = {user_id}
- IMPORTANT: Filter by type='expense' or type='income' accurately. 
  - If the user asks for "total spending", use type='expense'.
  - If the user asks for "total income", use type='income'.
  - If the user asks for "balance", use SUM(CASE WHEN type='income' THEN amount ELSE -amount END).
- For date ranges use ISO-8601 strings (e.g. '{month}-01' for start of current month).
- For "this week" use date('{today}','-6 days') as the lower bound.
- Aliases make column names readable (e.g. SUM(amount) AS total).
- LIMIT results to 50 rows unless the user asks for more.
"""


# ─── Pipeline steps ───────────────────────────────────────────────────────────

def _generate_sql(query_text: str, history: list[dict] = None, user_id: int = 0) -> str:
    """Step 1 — ask the LLM to produce a SELECT statement scoped to user_id."""
    system_prompt = SQL_SYSTEM_PROMPT_TEMPLATE.format(
        today=TODAY,
        schema=DB_SCHEMA,
        user_id=user_id,
        month=TODAY[:7],
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": query_text})

    response = client.beta.chat.completions.parse(
        model=OPENAI_MODEL,
        response_format=SQLResponse,
        messages=messages,
        temperature=0,
    )
    return response.choices[0].message.parsed.sql


def _validate_sql(sql: str) -> str:
    """Step 2 — reject anything that isn't a SELECT (safety guard)."""
    normalised = sql.lstrip().upper()
    if not normalised.startswith("SELECT"):
        raise ValueError(
            f"Only SELECT statements are allowed. Got: {sql[:80]!r}"
        )
    return sql


def _execute_sql(sql: str) -> list[dict]:
    """Step 3 — run the query and return rows as list-of-dicts."""
    return run_query(sql)


def _format_result(rows: list[dict]) -> str:
    """Step 4 — serialise to JSON string for the tool-result message."""
    if not rows:
        return json.dumps({"result": "No matching expenses found."})
    return json.dumps({"rows": rows}, default=str)


# ─── Public dispatcher ────────────────────────────────────────────────────────

def execute_read_expenses(query_text: str, history: list[dict] = None, user_id: int = 0) -> str:
    """
    Full Text-to-SQL pipeline scoped to a specific user.
    Returns a JSON string that is sent back to the LLM as the tool result.
    """
    sql = _generate_sql(query_text, history=history, user_id=user_id)
    sql = _validate_sql(sql)
    rows = _execute_sql(sql)
    return _format_result(rows)



def summarize_results(user_input: str, tool_result: str, history: list[dict] = None):
    """
    Takes the raw JSON rows string from execute_read_expenses and the original user query,
    and returns a conversational natural-language answer.
    """
    system_prompt = (
        "You are a helpful, extremely engaging financial assistant. "
        "Answer the user's question based strictly on the provided database results (amount is in ₹). "
        "IMPORTANT FORMATTING RULES:\n"
        "1. Use Markdown (bold, italics) to highlight important figures, totals, or categories.\n"
        "2. If listing multiple transactions, periods, or comparative data points, ALWAYS format them as a neat Markdown table.\n"
        "3. Sprinkle 1-2 relevant emojis (like 🍕, 🚗, 💰) per response to make it feel alive without overdoing it.\n"
        "Do not expose the raw JSON or IDs, format it naturally."
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": f"User question: {user_input}\n\nDatabase results:\n{tool_result}"})

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.3,
        stream=True,
    )
    return response
