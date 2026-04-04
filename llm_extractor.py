import json
from datetime import date
from openai import OpenAI
from models import Expense
from config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

TODAY = date.today().isoformat()

SYSTEM_PROMPT = f"""You are a professional personal finance extraction assistant.
Today's date is {TODAY}.

From the user's natural language input, extract the following fields into a JSON object:
- amount (float): the monetary amount.
- type (string): 'expense' (spending) or 'income' (receiving).
- category (string): choose the MOST relevant category from this list:
    - shopping: clothing, electronics, household items, beauty, gifts.
    - transport: fuel, taxi, bus, train, tolls, parking, vehicle maintenance.
    - entertainment: movies, streaming (Netflix/Spotify), games, concerts, sports, hobbies.
    - health: medicines, doctor visits, hospital bills, fitness, gym, pharmacy.
    - utilities: electricity, water, gas, internet, mobile recharge.
    - food: restaurants, cafes, groceries, snacks, drinks.
    - salary: internal income from work (Type should be 'income').
    - gift: money received as a gift (income) or spent on others (expense).
    - investment: stocks, mutual funds, savings, insurance premiums.
    - other: anything that does not fit the above.
- date (string): in YYYY-MM-DD format; use today's date ({TODAY}) if not explicitly mentioned.
- payment_mode (string): e.g., cash, UPI, bank transfer, credit card, debit card; default to "cash" if not mentioned.
- description (string): brief noun phrase describing the transaction.

Respond ONLY with a valid JSON object. Do not include any explanations or markdown.
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

You are given raw text from an OCR engine. Analyze it and extract transaction details into a JSON object:
- amount (float): the total monetary amount spent (look for "Total", "Grand Total"). If unclear, look for the largest number near the bottom.
- type: ALWAYS 'expense'.
- category (string): choose the MOST relevant category based on items or merchant from this list:
    - food: restaurants, cafes, groceries, bakeries, bars.
    - shopping: clothing, electronics, department stores, pharmacy (if non-medical), home goods.
    - transport: fuel/gas stations, taxi receipts, parking.
    - entertainment: cinema tickets, concert passes, hobby shops.
    - health: hospitals, clinics, specialized medical labs.
    - utilities: bills for electricity, water, or mobile service providers.
    - other: catch-all for miscellaneous receipts.
- date (string): the transaction date in YYYY-MM-DD format. If not found, use {TODAY}.
- payment_mode (string): e.g., cash, UPI, credit card, debit card. Default to "cash" if unclear.
- description (string): the merchant name or a brief summary of the primary items (e.g., "Starbucks Coffee").

Respond ONLY with a valid JSON object. If the text is unreadable or non-financial, return amount 0.0 and description "Failed to parse receipt".
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
