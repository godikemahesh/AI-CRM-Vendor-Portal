"""
HobbyFi Copilot — Database Layer
SQLite with aiosqlite for async operations.
Defines the full CRM schema + AI system tables (conversations, pending actions, audit).
"""
import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent / "hobbyfi.db"


def _row_to_dict(row: aiosqlite.Row) -> dict:
    """Convert a sqlite Row to a plain dict for JSON serialisation."""
    return dict(row)


async def get_db() -> aiosqlite.Connection:
    """Open a connection with dict-style row access."""
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """Create all tables if they don't exist."""
    db = await get_db()
    await db.executescript(_SCHEMA_SQL)
    await db.commit()
    await db.close()


async def fetch_all(db: aiosqlite.Connection, query: str, params=()) -> list[dict]:
    """Run a SELECT and return all rows as dicts."""
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [_row_to_dict(r) for r in rows]


async def fetch_one(db: aiosqlite.Connection, query: str, params=()) -> dict | None:
    """Run a SELECT and return a single row as dict (or None)."""
    cursor = await db.execute(query, params)
    row = await cursor.fetchone()
    return _row_to_dict(row) if row else None


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_SCHEMA_SQL = """
-- ===== CRM Core Tables =====

CREATE TABLE IF NOT EXISTS vendors (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    business_name TEXT NOT NULL,
    city        TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS activities (
    id          TEXT PRIMARY KEY,
    vendor_id   TEXT NOT NULL,
    name        TEXT NOT NULL,
    category    TEXT,
    hourly_rate REAL NOT NULL,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (vendor_id) REFERENCES vendors(id)
);

CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT,
    phone       TEXT,
    city        TEXT,
    joined_date TEXT DEFAULT (date('now')),
    status      TEXT DEFAULT 'active' CHECK(status IN ('active','inactive'))
);

CREATE TABLE IF NOT EXISTS memberships (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    activity_id TEXT NOT NULL,
    type        TEXT NOT NULL CHECK(type IN ('trial','monthly','quarterly','annual')),
    start_date  TEXT NOT NULL,
    end_date    TEXT NOT NULL,
    status      TEXT DEFAULT 'active' CHECK(status IN ('active','expired','cancelled')),
    amount      REAL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (activity_id) REFERENCES activities(id)
);

CREATE TABLE IF NOT EXISTS bookings (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    activity_id TEXT NOT NULL,
    date        TEXT NOT NULL,
    time_slot   TEXT NOT NULL,
    amount      REAL NOT NULL,
    status      TEXT DEFAULT 'confirmed'
                CHECK(status IN ('confirmed','cancelled','completed')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (activity_id) REFERENCES activities(id)
);

CREATE TABLE IF NOT EXISTS payments (
    id            TEXT PRIMARY KEY,
    booking_id    TEXT,
    membership_id TEXT,
    user_id       TEXT NOT NULL,
    amount        REAL NOT NULL,
    status        TEXT DEFAULT 'paid' CHECK(status IN ('paid','pending','refunded')),
    date          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ===== AI System Tables =====

CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    vendor_id   TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now')),
    summary     TEXT,
    FOREIGN KEY (vendor_id) REFERENCES vendors(id)
);

CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL CHECK(role IN ('user','assistant','system','tool')),
    content         TEXT NOT NULL,
    tool_calls      TEXT,          -- JSON blob
    timestamp       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS pending_actions (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT,
    tool_name       TEXT NOT NULL,
    params          TEXT NOT NULL,  -- JSON
    description     TEXT NOT NULL,
    before_state    TEXT,           -- JSON
    after_state     TEXT,           -- JSON
    status          TEXT DEFAULT 'pending'
                    CHECK(status IN ('pending','approved','rejected','expired')),
    created_at      TEXT DEFAULT (datetime('now')),
    resolved_at     TEXT,
    resolved_by     TEXT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id               TEXT PRIMARY KEY,
    action_type      TEXT NOT NULL CHECK(action_type IN ('read','write','approval')),
    tool_name        TEXT,
    params           TEXT,          -- JSON
    result           TEXT,          -- JSON
    vendor_id        TEXT,
    affected_user_id TEXT,
    approved_by      TEXT,
    timestamp        TEXT DEFAULT (datetime('now'))
);
"""
