"""
db.py — Database abstraction layer.

Supports two backends, selected by the DATABASE_URL environment variable:
  - PostgreSQL (Neon or any Postgres)  when DATABASE_URL is set
  - SQLite                              when DATABASE_URL is NOT set (local dev)

The public API is identical in both cases:
    init_db()              -> None
    insert_expense(e)      -> int   (new row id)
    run_query(sql, params) -> list[dict]

SQL dialect differences handled internally:
  - SQLite uses  ?  placeholders and AUTOINCREMENT
  - Postgres uses %s placeholders and SERIAL / RETURNING id
"""
import sqlite3
from datetime import datetime, timezone

from models import Expense
from config import DB_PATH, DATABASE_URL


# ── Backend detection ─────────────────────────────────────────────────────────

_USE_POSTGRES = bool(DATABASE_URL)


# ── PostgreSQL helpers ────────────────────────────────────────────────────────

def _pg_conn():
    """Return a psycopg2 connection to Neon/Postgres."""
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    return conn


# ── SQLite helpers ────────────────────────────────────────────────────────────

def _sqlite_conn() -> sqlite3.Connection:
    """Return a sqlite3 connection."""
    return sqlite3.connect(DB_PATH)


# ── Public API ────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create tables and run any pending migrations."""
    if _USE_POSTGRES:
        conn = _pg_conn()
        try:
            with conn.cursor() as cur:
                # users table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id            SERIAL PRIMARY KEY,
                        username      TEXT NOT NULL,
                        email         TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        created_at    TEXT NOT NULL
                    )
                """)
                # expenses table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS expenses (
                        id           SERIAL PRIMARY KEY,
                        user_id      INTEGER NOT NULL DEFAULT 0,
                        amount       REAL        NOT NULL,
                        category     TEXT        NOT NULL,
                        date         TEXT        NOT NULL,
                        payment_mode TEXT        NOT NULL,
                        description  TEXT        NOT NULL,
                        type         TEXT        NOT NULL DEFAULT 'expense',
                        created_at   TEXT        NOT NULL
                    )
                """)
                # chat_messages table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id           SERIAL PRIMARY KEY,
                        user_id      INTEGER NOT NULL DEFAULT 0,
                        role         TEXT    NOT NULL,
                        content      TEXT    NOT NULL,
                        created_at   TEXT    NOT NULL
                    )
                """)
                # budgets table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS budgets (
                        id           SERIAL PRIMARY KEY,
                        user_id      INTEGER NOT NULL,
                        category     TEXT    NOT NULL,
                        amount       REAL    NOT NULL,
                        period       TEXT    NOT NULL DEFAULT 'monthly',
                        created_at   TEXT    NOT NULL,
                        UNIQUE(user_id, category, period)
                    )
                """)
                # migration: add user_id if missing
                cur.execute("""
                    ALTER TABLE expenses ADD COLUMN IF NOT EXISTS user_id INTEGER NOT NULL DEFAULT 0
                """)
                # migration: add type if missing
                cur.execute("""
                    ALTER TABLE expenses ADD COLUMN IF NOT EXISTS type TEXT NOT NULL DEFAULT 'expense'
                """)
            conn.commit()
        finally:
            conn.close()
    else:
        with _sqlite_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    username      TEXT NOT NULL,
                    email         TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at    TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id      INTEGER NOT NULL DEFAULT 0,
                    amount       REAL    NOT NULL,
                    category     TEXT    NOT NULL,
                    date         TEXT    NOT NULL,
                    payment_mode TEXT    NOT NULL,
                    description  TEXT    NOT NULL,
                    type         TEXT    NOT NULL DEFAULT 'expense',
                    created_at   TEXT    NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id      INTEGER NOT NULL DEFAULT 0,
                    role         TEXT    NOT NULL,
                    content      TEXT    NOT NULL,
                    created_at   TEXT    NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS budgets (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id      INTEGER NOT NULL,
                    category     TEXT    NOT NULL,
                    amount       REAL    NOT NULL,
                    period       TEXT    NOT NULL DEFAULT 'monthly',
                    created_at   TEXT    NOT NULL,
                    UNIQUE(user_id, category, period)
                )
            """)
            # migration: add user_id column if it doesn't exist yet
            existing = conn.execute("PRAGMA table_info(expenses)").fetchall()
            col_names = [row[1] for row in existing]
            if "user_id" not in col_names:
                conn.execute("ALTER TABLE expenses ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0")
            if "type" not in col_names:
                conn.execute("ALTER TABLE expenses ADD COLUMN type TEXT NOT NULL DEFAULT 'expense'")
            conn.commit()


def insert_expense(expense: Expense, user_id: int = 0) -> int:
    """Insert an Expense record and return the new row id."""
    created_at = datetime.now(timezone.utc).isoformat()

    if _USE_POSTGRES:
        conn = _pg_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO expenses (user_id, amount, category, date, payment_mode, description, type, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_id,
                        expense.amount,
                        expense.category,
                        expense.date,
                        expense.payment_mode,
                        expense.description,
                        expense.type,
                        created_at,
                    ),
                )
                row_id = cur.fetchone()[0]
            conn.commit()
            return row_id
        finally:
            conn.close()
    else:
        with _sqlite_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO expenses (user_id, amount, category, date, payment_mode, description, type, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    expense.amount,
                    expense.category,
                    expense.date,
                    expense.payment_mode,
                    expense.description,
                    expense.type,
                    created_at,
                ),
            )
            conn.commit()
            return cursor.lastrowid


# ── User helpers ──────────────────────────────────────────────────────────────

def insert_user(username: str, email: str, password_hash: str) -> int:
    """Insert a new user and return their new id. Raises on duplicate email."""
    created_at = datetime.now(timezone.utc).isoformat()
    if _USE_POSTGRES:
        conn = _pg_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (username, email, password_hash, created_at)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (username, email, password_hash, created_at),
                )
                row_id = cur.fetchone()[0]
            conn.commit()
            return row_id
        finally:
            conn.close()
    else:
        with _sqlite_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (username, email, password_hash, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, email, password_hash, created_at),
            )
            conn.commit()
            return cursor.lastrowid


def get_user_by_email(email: str) -> dict | None:
    """Return the user row as a dict, or None if not found."""
    rows = run_query("SELECT * FROM users WHERE email = ?", (email,))
    return rows[0] if rows else None


def get_user_by_id(user_id: int) -> dict | None:
    """Return the user row as a dict, or None if not found."""
    rows = run_query("SELECT * FROM users WHERE id = ?", (user_id,))
    return rows[0] if rows else None


def run_query(sql: str, params: tuple = ()) -> list[dict]:
    """Execute a SQL statement and return rows as list-of-dicts.

    Works for both SELECT (returns rows) and any other statement.
    Placeholder style is automatically adapted to the active backend.
    """
    if _USE_POSTGRES:
        import psycopg2.extras
        # Postgres uses %s placeholders; SQLite uses ?
        pg_sql = sql.replace("?", "%s")
        conn = _pg_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(pg_sql, params)
                try:
                    rows = cur.fetchall()
                    return [dict(r) for r in rows]
                except Exception:
                    return []
        finally:
            conn.close()
    else:
        with _sqlite_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


# ── Chat history helpers ──────────────────────────────────────────────────────

def get_chat_history(user_id: int, limit: int = 8) -> list[dict]:
    """Fetch the most recent chat messages for a user, returned in chronological order."""
    # We fetch the most recent ones first, then reverse them so they are in order for the LLM.
    sql = """
        SELECT role, content 
        FROM chat_messages 
        WHERE user_id = ? 
        ORDER BY id DESC 
        LIMIT ?
    """
    rows = run_query(sql, (user_id, limit))
    return list(reversed(rows))


def insert_chat_message(user_id: int, role: str, content: str) -> None:
    """Save a new message turn to the database."""
    created_at = datetime.now(timezone.utc).isoformat()
    if _USE_POSTGRES:
        conn = _pg_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO chat_messages (user_id, role, content, created_at) VALUES (%s, %s, %s, %s)",
                    (user_id, role, content, created_at)
                )
            conn.commit()
        finally:
            conn.close()
    else:
        with _sqlite_conn() as conn:
            conn.execute(
                "INSERT INTO chat_messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (user_id, role, content, created_at)
            )
            conn.commit()


def clear_chat_history(user_id: int) -> None:
    """Delete all chat history for a specific user."""
    if _USE_POSTGRES:
        conn = _pg_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM chat_messages WHERE user_id = %s", (user_id,))
            conn.commit()
        finally:
            conn.close()
    else:
        with _sqlite_conn() as conn:
            conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
            conn.commit()


# ── Budget helpers ────────────────────────────────────────────────────────────

def upsert_budget(user_id: int, category: str, amount: float, period: str = 'monthly') -> None:
    """Create or update a budget for a user and category."""
    created_at = datetime.now(timezone.utc).isoformat()
    category = category.lower()

    if _USE_POSTGRES:
        conn = _pg_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO budgets (user_id, category, amount, period, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT(user_id, category, period) 
                    DO UPDATE SET amount = EXCLUDED.amount, created_at = EXCLUDED.created_at
                    """,
                    (user_id, category, amount, period, created_at)
                )
            conn.commit()
        finally:
            conn.close()
    else:
        with _sqlite_conn() as conn:
            conn.execute(
                """
                INSERT INTO budgets (user_id, category, amount, period, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, category, period) 
                DO UPDATE SET amount = excluded.amount, created_at = excluded.created_at
                """,
                (user_id, category, amount, period, created_at)
            )
            conn.commit()


def get_budgets(user_id: int) -> list[dict]:
    """Return all budgets for a specific user."""
    sql = "SELECT category, amount, period FROM budgets WHERE user_id = ?"
    return run_query(sql, (user_id,))
