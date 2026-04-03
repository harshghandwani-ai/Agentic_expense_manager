"""
routers/expenses.py -- FastAPI router for all expense endpoints.

Endpoints:
  POST /api/expenses              -- log from natural language
  POST /api/expenses/query        -- query in natural language
  POST /api/expenses/upload       -- receipt image -> ExpensePreview (NO DB save)
  POST /api/expenses/confirm      -- save confirmed/edited preview to DB
  GET  /api/expenses/stats        -- statistics
  GET  /api/expenses/export       -- CSV download
  GET  /api/expenses              -- list with filters
"""
import csv
import io
import json
import os
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, File
from openai import OpenAI

from auth_utils import TokenData, get_current_user
from db import insert_expense, run_query
from llm_extractor import extract_expense
from models import Expense
from ocr import get_engine
from query_engine import _generate_sql, _validate_sql, _execute_sql
from schemas import (
    ConfirmRequest,
    ExpensePreview,
    ExpenseRecord,
    LogRequest,
    LogResponse,
    QueryRequest,
    QueryResponse,
)
from config import OPENAI_API_KEY, OPENAI_MODEL

router = APIRouter()

_client = OpenAI(api_key=OPENAI_API_KEY)

TODAY = date.today().isoformat()

# -- Query summarisation prompt ----------------------------------------

_SUMMARY_SYSTEM = (
    "You are a helpful expense assistant. "
    "Given a user question and raw database results in JSON, "
    "write a concise, friendly natural-language answer. "
    "Use currency amounts naturally. "
    "If there are no results, say so politely."
)


def _summarise(question: str, rows: list[dict], sql: str) -> str:
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


# -- POST /api/expenses ------------------------------------------------

@router.post(
    "",
    response_model=LogResponse,
    status_code=201,
    summary="Log a new expense",
)
async def log_expense(
    body: LogRequest,
    current_user: TokenData = Depends(get_current_user),
) -> LogResponse:
    try:
        expense = extract_expense(body.text)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"LLM extraction failed: {exc}") from exc
    try:
        row_id = insert_expense(expense, user_id=current_user.user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database insert failed: {exc}") from exc
    rows = run_query("SELECT * FROM expenses WHERE id = ? AND user_id = ?", (row_id, current_user.user_id))
    if not rows:
        raise HTTPException(status_code=500, detail="Expense saved but could not be retrieved.")
    return LogResponse(**rows[0])


# -- POST /api/expenses/query ------------------------------------------

@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Query expenses in natural language",
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
        answer = f"Query returned {len(rows)} row(s). (Summarisation failed: {exc})"
    return QueryResponse(answer=answer, sql=sql, rows=rows)


# -- GET /api/expenses/stats -------------------------------------------

@router.get("/stats", summary="Get financial statistics")
async def get_stats(
    current_user: TokenData = Depends(get_current_user),
) -> dict:
    try:
        # Total Expenses
        exp_rows = run_query(
            "SELECT SUM(amount) as total FROM expenses WHERE user_id = ? AND type = 'expense'",
            (current_user.user_id,),
        )
        total_expenses = exp_rows[0]["total"] if exp_rows and exp_rows[0]["total"] else 0.0

        # Total Income
        inc_rows = run_query(
            "SELECT SUM(amount) as total FROM expenses WHERE user_id = ? AND type = 'income'",
            (current_user.user_id,),
        )
        total_income = inc_rows[0]["total"] if inc_rows and inc_rows[0]["total"] else 0.0

        # Top Categories (Spending ONLY)
        cat_rows = run_query(
            "SELECT LOWER(category) as category, SUM(amount) as total FROM expenses "
            "WHERE user_id = ? AND type = 'expense' "
            "GROUP BY LOWER(category) ORDER BY total DESC LIMIT 4",
            (current_user.user_id,),
        )
        categories = [{"name": r["category"], "amount": r["total"]} for r in cat_rows]

        return {
            "total_expenses": total_expenses, 
            "total_income": total_income,
            "top_categories": categories
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database query failed: {exc}") from exc


# -- GET /api/expenses/export ------------------------------------------

@router.get("/export", summary="Export expenses to CSV")
async def export_csv(
    current_user: TokenData = Depends(get_current_user),
):
    try:
        rows = run_query(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC, id DESC",
            (current_user.user_id,),
        )
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["id","amount","category","date","payment_mode","description","created_at"],
        )
        writer.writeheader()
        writer.writerows(rows)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="expenses.csv"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database export failed: {exc}") from exc


# -- POST /api/expenses/upload  (OCR + LLM preview, NO DB save) --------

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_MIME_PREFIXES = ("image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff")


@router.post(
    "/upload",
    response_model=ExpensePreview,
    status_code=200,
    summary="Upload a receipt image (preview only)",
)
async def upload_image(
    file: UploadFile = File(...),
    current_user: TokenData = Depends(get_current_user),
) -> ExpensePreview:
    content_type = file.content_type or ""
    if not any(content_type.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type {content_type!r}. Please upload JPEG, PNG, WebP, BMP, or TIFF.",
        )
    try:
        file_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read uploaded file: {exc}") from exc
    if len(file_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large ({len(file_bytes)//(1024*1024)} MB). Max 10 MB.",
        )
    original_name = os.path.basename(file.filename or "upload")
    safe_filename = f"{uuid.uuid4().hex}_{original_name}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    try:
        with open(file_path, "wb") as f:
            f.write(file_bytes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save image to disk: {exc}") from exc
    try:
        raw_text: str = get_engine().extract_raw_text(os.path.abspath(file_path))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {exc}") from exc
    if not raw_text.strip():
        raise HTTPException(
            status_code=422,
            detail="No readable text detected. Please upload a clear photo of a receipt.",
        )
    try:
        expense = extract_expense(raw_text)
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not extract expense from image text: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM extraction failed: {exc}") from exc
    return ExpensePreview(
        amount=expense.amount,
        category=expense.category,
        date=expense.date,
        payment_mode=expense.payment_mode,
        description=expense.description,
        ocr_text=raw_text,
        source="image",
    )


# -- POST /api/expenses/confirm  (save confirmed expense to DB) ----------

@router.post(
    "/confirm",
    response_model=LogResponse,
    status_code=201,
    summary="Confirm and save an expense",
    description=(
        "Takes the (possibly user-edited) fields and saves them to the DB. "
        "Call this after /upload or after a log intent from /api/chat."
    ),
)
async def confirm_expense(
    body: ConfirmRequest,
    current_user: TokenData = Depends(get_current_user),
) -> LogResponse:
    try:
        expense = Expense(
            amount=body.amount,
            category=body.category,
            date=body.date,
            payment_mode=body.payment_mode,
            description=body.description,
            type=body.type,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid expense data: {exc}") from exc
    try:
        row_id = insert_expense(expense, user_id=current_user.user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database insert failed: {exc}") from exc
    rows = run_query("SELECT * FROM expenses WHERE id = ? AND user_id = ?", (row_id, current_user.user_id))
    if not rows:
        raise HTTPException(status_code=500, detail="Expense was saved but could not be retrieved.")
    return LogResponse(**rows[0])


# -- GET /api/expenses  (list with optional filters) --------------------

@router.get(
    "",
    response_model=list[ExpenseRecord],
    summary="List expenses",
)
async def list_expenses(
    current_user: TokenData = Depends(get_current_user),
    category: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> list[ExpenseRecord]:
    conditions: list[str] = ["user_id = ?"]
    params: list = [current_user.user_id]
    if category:
        conditions.append("LOWER(category) = LOWER(?)")
        params.append(category)
    if date_from:
        conditions.append("date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date <= ?")
        params.append(date_to)
    where = "WHERE " + " AND ".join(conditions)
    sql = f"SELECT * FROM expenses {where} ORDER BY date DESC, id DESC LIMIT {limit}"
    try:
        rows = run_query(sql, tuple(params))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database query failed: {exc}") from exc
    return [ExpenseRecord(**row) for row in rows]
