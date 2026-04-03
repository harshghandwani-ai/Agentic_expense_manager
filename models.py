from pydantic import BaseModel, Field


class Expense(BaseModel):
    amount: float = Field(..., description="The monetary amount")
    category: str = Field(..., description="Category of transaction e.g. food, salary, shopping")
    date: str = Field(..., description="Date of transaction in YYYY-MM-DD format")
    payment_mode: str = Field(..., description="Payment method e.g. cash, UPI, bank transfer")
    description: str = Field(..., description="Brief description of the transaction")
    type: str = Field("expense", description="The type of transaction: 'expense' or 'income'")
