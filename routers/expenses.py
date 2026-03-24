"""
routers/expenses.py — FastAPI router with 3 expense endpoints.

Endpoints:
  POST /api/expenses          — log a new expense from natural language
  POST /api/expenses/query    — query past expenses in natural language
  GET  /api/expenses          — list expenses with optional filters
"""
import csv
import io
import json
import os
import shutil
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response, UploadFile, File
from openai import OpenAI

from db import insert_expense, run_query
from llm_extractor import extract_expense
from query_engine import _generate_sql, _validate_sql, _execute_sql
from schemas import ExpenseRecord, LogRequest, LogResponse, QueryRequest, QueryResponse
from config import OPENAI_API_KEY, OPENAI_MODEL

router = APIRouter()

_client = OpenAI(api_key=OPENAI_API_KEY)

TODAY = date.today().isoformat()

# ── Query summarisation prompt ────────────────────────────────────────────────
_SUMMARY_SYSTEM = (
    "You are a helpful expense assistant. "
    "Given a user question and raw database results in JSON, "
    "write a concise, friendly natural-language answer. "
    "Use currency amounts naturally (no symbol needed if unclear). "
    "If there are no results, say so politely."
)


def _summarise(question: str, rows: list[dict], sql: str) -> str:
    """Ask the LLM to turn raw rows into a human-readable answer."""
    payload = json.dumps({"question": question, "sql": sql, "rows": rows}, default=str)
    response = _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {"role": "user", "content": payload},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


# ── POST /api/expenses — log a new expense ────────────────────────────────────

@router.post(
    "",
    response_model=LogResponse,
    status_code=201,
    summary="Log a new expense",
    description="Extract structured fields from natural-language text and save to the database.",
)
async def log_expense(body: LogRequest) -> LogResponse:
    try:
        expense = extract_expense(body.text)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"LLM extraction failed: {exc}") from exc

    try:
        row_id = insert_expense(expense)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database insert failed: {exc}") from exc

    # Fetch the saved row to include created_at
    rows = run_query("SELECT * FROM expenses WHERE id = ?", (row_id,))
    if not rows:
        raise HTTPException(status_code=500, detail="Expense saved but could not be retrieved.")
    return LogResponse(**rows[0])


# ── POST /api/expenses/query — natural-language query ────────────────────────

@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Query expenses in natural language",
    description=(
        "Translates a natural-language question into SQL, executes it, "
        "and returns both raw rows and an AI-generated summary."
    ),
)
async def query_expenses(body: QueryRequest) -> QueryResponse:
    try:
        sql = _generate_sql(body.question)
        sql = _validate_sql(sql)
        rows = _execute_sql(sql)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query pipeline failed: {exc}") from exc

    try:
        answer = _summarise(body.question, rows, sql)
    except Exception as exc:
        # Summarisation is best-effort; fallback to raw JSON string
        answer = f"Query returned {len(rows)} row(s). (Summarisation failed: {exc})"

    return QueryResponse(answer=answer, sql=sql, rows=rows)


# ── GET /api/expenses/stats — get expense statistics ────────────────────────

@router.get(
    "/stats",
    summary="Get expense statistics",
    description="Return total expenses and top categories.",
)
async def get_stats() -> dict:
    try:
        # Total expenses
        total_rows = run_query("SELECT SUM(amount) as total FROM expenses")
        total = total_rows[0]["total"] if total_rows and total_rows[0]["total"] else 0.0

        # Top categories (top 4)
        cat_rows = run_query("""
            SELECT category, SUM(amount) as total 
            FROM expenses 
            GROUP BY LOWER(category) 
            ORDER BY total DESC 
            LIMIT 4
        """)
        
        categories = [{"name": row["category"], "amount": row["total"]} for row in cat_rows]
        
        return {
            "total_expenses": total,
            "top_categories": categories
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database query failed: {exc}") from exc


# ── GET /api/expenses/export — export expenses to CSV ─────────────────────────

@router.get(
    "/export",
    summary="Export expenses to CSV",
    description="Download all expenses as a CSV file.",
)
async def export_csv():
    try:
        rows = run_query("SELECT * FROM expenses ORDER BY date DESC, id DESC")
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["id", "amount", "category", "date", "payment_mode", "description", "created_at"])
        writer.writeheader()
        writer.writerows(rows)
        
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="expenses.csv"'}
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database export failed: {exc}") from exc


# ── POST /api/expenses/upload — upload an image ───────────────────────────────

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post(
    "/upload",
    summary="Upload an image",
    description="Upload an image (e.g. receipt). Currently just saves it to disk.",
)
async def upload_image(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"status": "success", "filename": file.filename, "message": "Image uploaded successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {exc}") from exc


# ── GET /api/expenses — list expenses with optional filters ───────────────────

@router.get(
    "",
    response_model=list[ExpenseRecord],
    summary="List expenses",
    description="Return expenses with optional filters for category, date range, and limit.",
)
async def list_expenses(
    category: Optional[str] = Query(None, description="Filter by category (e.g. food, shopping)"),
    date_from: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    date_to: Optional[str] = Query(None, description="End date in YYYY-MM-DD format (defaults to today)"),
    limit: int = Query(50, ge=1, le=500, description="Max rows to return"),
) -> list[ExpenseRecord]:
    conditions: list[str] = []
    params: list = []

    if category:
        conditions.append("LOWER(category) = LOWER(?)")
        params.append(category)
    if date_from:
        conditions.append("date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date <= ?")
        params.append(date_to)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM expenses {where} ORDER BY date DESC, id DESC LIMIT {limit}"

    try:
        rows = run_query(sql, tuple(params))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database query failed: {exc}") from exc

    return [ExpenseRecord(**row) for row in rows]
