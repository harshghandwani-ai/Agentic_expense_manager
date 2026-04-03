import json
from datetime import date
from openai import OpenAI
from models import Expense
from config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

TODAY = date.today().isoformat()

SYSTEM_PROMPT = f"""You are a personal finance extraction assistant.
Today's date is {TODAY}.

From the user's natural language input, extract:
- amount (float): the monetary amount
- category (string): category e.g. food, salary, shopping, transport, entertainment, health, utilities, other
- date (string): in YYYY-MM-DD format; use today's date if not specified
- payment_mode (string): e.g. cash, UPI, bank transfer, credit card, debit card; default to "cash" if not mentioned
- description (string): brief noun phrase describing the transaction
- type (string): either 'expense' (spending money) or 'income' (receiving money). 

Respond ONLY with a valid JSON object matching this schema exactly. No explanation, no markdown.
"""


def extract_expense(text: str) -> Expense:
    """Call OpenAI to extract structured expense data from natural language."""
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)
    return Expense(**data)


RECEIPT_SYSTEM_PROMPT = f"""You are an expert OCR receipt parsing assistant.
Today's date is {TODAY}.

You are given raw text extracted from an image by an OCR engine. The text might be messy, scattered, or contain typos.
Analyze the OCR text and extract the transaction details into the following schema:
- amount (float): the total monetary amount spent (look for "Total", "Amount", etc.). If multiple amounts exist, try to find the final total.
- category (string): guess the category based on the items or merchant. Must be one of: food, shopping, transport, entertainment, health, utilities, other.
- date (string): the transaction date in YYYY-MM-DD format. If none is found, use today's date: {TODAY}.
- payment_mode (string): how it was paid (cash, UPI, credit card, debit card, etc.). Default to "cash" if unclear.
- description (string): a brief noun phrase of what was bought or the merchant name (e.g., "Starbucks coffee" or "Grocery run at Walmart").
- type (string): ALWAYS 'expense' for receipts unless it is explicitly an income/receive voucher (very rare).

Respond ONLY with a valid JSON object matching this schema exactly. No explanation, no markdown.
If the text contains completely unrelated junk and no monetary value or purchase context can be found, you must still output valid JSON with amount=0.0 and description="Failed to parse receipt" and type="expense".
"""


def extract_expense_from_receipt(ocr_text: str) -> Expense:
    """Call OpenAI to extract structured expense data from messy OCR strings."""
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": RECEIPT_SYSTEM_PROMPT},
            {"role": "user", "content": ocr_text},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)
    return Expense(**data)
