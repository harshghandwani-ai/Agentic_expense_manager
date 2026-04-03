"""
schemas.py — API-level Pydantic models for request and response shapes.

Includes ChatRequest/ChatResponse for the unified /api/chat endpoint.

Kept separate from models.py (domain Expense) for clean layering.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Request models ────────────────────────────────────────────────────────────

class LogRequest(BaseModel):
    text: str = Field(
        ...,
        description="Natural-language expense description.",
        examples=["I spent 500 on shoes today using UPI"],
    )


class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        description="Natural-language question about past expenses.",
        examples=["How much did I spend this month?"],
    )


# ── Response models ───────────────────────────────────────────────────────────

class LogResponse(BaseModel):
    id: int
    amount: float
    category: str
    date: str
    payment_mode: str
    description: str
    type: str
    created_at: str


class QueryResponse(BaseModel):
    answer: str = Field(..., description="AI-generated natural-language answer.")
    sql: str = Field(..., description="The SQL query that was executed.")
    rows: list[dict[str, Any]] = Field(..., description="Raw result rows from the database.")


class ExpenseRecord(BaseModel):
    id: int
    amount: float
    category: str
    date: str
    payment_mode: str
    description: str
    type: str
    created_at: str


# ── Preview / Confirm (two-step logging) ─────────────────────────────────────

class ExpensePreview(BaseModel):
    """
    Extracted expense/income fields returned BEFORE the user confirms.
    """
    amount: float = Field(..., description="Monetary amount extracted by LLM.")
    category: str = Field(..., description="Category of the transaction.")
    date: str = Field(..., description="Date in YYYY-MM-DD format.")
    payment_mode: str = Field(..., description="e.g. cash, UPI, bank transfer.")
    description: str = Field(..., description="Brief description of the transaction.")
    type: str = Field("expense", description="'expense' or 'income'")
    ocr_text: Optional[str] = Field(None, description="Raw PaddleOCR output.")
    source: Optional[str] = Field(None, description="'image' or 'text'")


class ConfirmRequest(BaseModel):
    """
    Fields the user submits when they click 'Confirm & Save'.
    """
    amount: float = Field(..., gt=0, description="Must be a positive number.")
    category: str = Field(..., description="Category of the transaction.")
    date: str = Field(..., description="Date in YYYY-MM-DD format.")
    payment_mode: str = Field(..., description="e.g. cash, UPI, bank transfer.")
    description: str = Field(..., description="Brief description of the transaction.")
    type: str = Field("expense", description="'expense' or 'income'")


# ── Chat (unified intent) models ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        description="Any natural-language input: log an expense, query history, or general chat.",
        examples=["I spent 350 on lunch", "how much did I spend today", "what can you do"],
    )


class ChatResponse(BaseModel):
    intent: str = Field(..., description="Detected intent: 'log', 'query', or 'chat'.")
    answer: str = Field(..., description="AI natural-language reply.")
    expense: Optional[ExpensePreview] = Field(
        None,
        description="Populated with an UNCONFIRMED preview when intent=='log'. "
                    "The frontend must call POST /api/expenses/confirm to save it.",
    )


# ── Budget & Stats models ─────────────────────────────────────────────────────

class BudgetStats(BaseModel):
    name: str = Field(..., description="Category name (or 'total')")
    amount: float = Field(..., description="Current total spent in this category.")
    budget: Optional[float] = Field(None, description="Current budget set for this category.")


class StatsResponse(BaseModel):
    total_expenses: float
    total_income: float
    top_categories: list[BudgetStats]


class BudgetUpsertRequest(BaseModel):
    category: str
    amount: float = Field(..., gt=0)
    period: str = "monthly"
