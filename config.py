import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
DB_PATH: str = os.getenv("DB_PATH", "expenses.db")

# Model used for all LLM calls (classification, extraction, chat)
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# When set, db.py uses PostgreSQL (Neon in production).
# When empty/unset, db.py falls back to SQLite for local development.
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_DAYS: int = 7

if not OPENAI_API_KEY:
    raise EnvironmentError(
        "OPENAI_API_KEY is not set. Please add it to a .env file or export it as an environment variable."
    )
