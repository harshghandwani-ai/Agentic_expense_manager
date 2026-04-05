import json
import time
import logging
import uuid
from datetime import date
from openai import OpenAI
from models import Expense
from config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

TODAY = date.today().isoformat()

SYSTEM_PROMPT = f"""You are a personal finance extraction assistant. Today is {TODAY}.

Extract the transaction details into a JSON object with strictly these keys:
- amount (float)
- type (string): 'expense' or 'income'
- category (string): choose from [shopping, transport, entertainment, health, utilities, food, salary, gift, investment, other]
- date (string): YYYY-MM-DD (default to {TODAY})
- payment_mode (string): e.g. cash, UPI, card (default 'cash')
- description (string): brief noun phrase describing the item/merchant

Respond ONLY with valid JSON. No explanations or markdown.
"""


def extract_expense(text: str) -> Expense:
    """Call OpenAI to extract structured expense data from natural language."""
    request_id = str(uuid.uuid4())
    t0 = time.time()
    response = client.beta.chat.completions.parse(
        model=OPENAI_MODEL,
        response_format=Expense,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0,
    )
    duration_ms = round((time.time() - t0) * 1000)
    logger.info(
        "[LATENCY] request_id=%s stage=text_extraction model=%s duration_ms=%d",
        request_id, OPENAI_MODEL, duration_ms
    )

    return response.choices[0].message.parsed


RECEIPT_SYSTEM_PROMPT = f"""You are an OCR receipt parsing assistant. Today is {TODAY}.

Extract transaction details from the raw OCR text into a JSON object with strictly these keys:
- amount (float): total spent. Look for "Total" or the largest number near the bottom.
- type (string): ALWAYS 'expense'
- category (string): choose from [food, shopping, transport, entertainment, health, utilities, other]
- date (string): YYYY-MM-DD (default to {TODAY})
- payment_mode (string): e.g. cash, UPI, card (default 'cash')
- description (string): merchant name or brief summary

If unreadable, return amount 0.0 and description "Failed to parse receipt".
Respond ONLY with valid JSON. No explanations or markdown.
"""


def extract_expense_from_receipt(ocr_text: str) -> Expense:
    """Call OpenAI to extract structured expense data from messy OCR strings."""
    request_id = str(uuid.uuid4())
    t0 = time.time()
    response = client.beta.chat.completions.parse(
        model=OPENAI_MODEL,
        response_format=Expense,
        messages=[
            {"role": "system", "content": RECEIPT_SYSTEM_PROMPT},
            {"role": "user", "content": ocr_text},
        ],
        temperature=0,
    )
    duration_ms = round((time.time() - t0) * 1000)
    logger.info(
        "[LATENCY] request_id=%s stage=receipt_extraction model=%s duration_ms=%d",
        request_id, OPENAI_MODEL, duration_ms
    )

    return response.choices[0].message.parsed
