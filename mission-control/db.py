#!/usr/bin/env python3
"""SQLite store for cairn's token-metering feature. stdlib only.

Usage:
    from db import connect, insert_call, insert_usage_limit_event, insert_tool_use, save_session_label,
                    save_session_version
    conn = connect(cairn_dir)   # opens/creates cairn_dir/tokens.db with tables
"""
import sqlite3
from pathlib import Path

DB_FILENAME = "tokens.db"

# Bumped whenever a schema change lands. `connect()` stamps this into
# `PRAGMA user_version` on every open so a future migration can tell an
# older `tokens.db` apart from the current shape. Every schema statement
# so far is `CREATE TABLE IF NOT EXISTS` (additive-only), so no separate
# migration function is needed yet — just the marker itself.
# 1: calls, usage_limit_events, tool_uses, session_labels.
# 2: adds session_versions (the cairn version each session started under).
SCHEMA_VERSION = 2

CALLS_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    request_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    agent TEXT,
    model TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_write_5m_tokens INTEGER NOT NULL DEFAULT 0,
    cache_write_1h_tokens INTEGER NOT NULL DEFAULT 0
)
"""

USAGE_LIMIT_EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_limit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    raw_entry TEXT NOT NULL
)
"""

TOOL_USES_SCHEMA = """
CREATE TABLE IF NOT EXISTS tool_uses (
    tool_use_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    agent TEXT,
    tool_name TEXT NOT NULL,
    detail TEXT,
    timestamp TEXT NOT NULL
)
"""

SESSION_LABELS_SCHEMA = """
CREATE TABLE IF NOT EXISTS session_labels (
    session_id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

SESSION_VERSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS session_versions (
    session_id TEXT PRIMARY KEY,
    cairn_version TEXT NOT NULL,
    recorded_at TEXT NOT NULL
)
"""

CALLS_SESSION_INDEX = "CREATE INDEX IF NOT EXISTS idx_calls_session_id ON calls (session_id)"
CALLS_TIMESTAMP_INDEX = "CREATE INDEX IF NOT EXISTS idx_calls_timestamp_trunc ON calls (substr(timestamp, 1, 19))"
TOOL_USES_SESSION_INDEX = "CREATE INDEX IF NOT EXISTS idx_tool_uses_session_id ON tool_uses (session_id)"
USAGE_LIMIT_EVENTS_SESSION_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_usage_limit_events_session_id ON usage_limit_events (session_id)"
)


def db_path(cairn_dir: Path) -> Path:
    return cairn_dir / DB_FILENAME


def connect(cairn_dir: Path) -> sqlite3.Connection:
    cairn_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path(cairn_dir))
    # WAL mode lets a writer (the parser) and a reader (the server) touch
    # the same file at once without contending destructively — set this
    # before any table exists so every subsequent connection sees it.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(CALLS_SCHEMA)
    conn.execute(USAGE_LIMIT_EVENTS_SCHEMA)
    conn.execute(TOOL_USES_SCHEMA)
    conn.execute(SESSION_LABELS_SCHEMA)
    conn.execute(SESSION_VERSIONS_SCHEMA)
    conn.execute(CALLS_SESSION_INDEX)
    conn.execute(CALLS_TIMESTAMP_INDEX)
    conn.execute(TOOL_USES_SESSION_INDEX)
    conn.execute(USAGE_LIMIT_EVENTS_SESSION_INDEX)
    current_version = conn.execute("PRAGMA user_version").fetchone()[0]
    if current_version < SCHEMA_VERSION:
        # A `tokens.db` written before this marker existed defaults to 0
        # here; stamping it now is a one-time no-op migration since every
        # schema statement above is already additive/idempotent.
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()
    return conn


def insert_call(conn, row: dict) -> None:
    """Insert one `calls`-shaped row. Idempotent on `request_id`.

    `row` carries the same keys as the `calls` table's columns; `agent`
    is optional (column is nullable), and the three cache-token fields
    default to 0 when absent from `row`.
    """
    conn.execute(
        "INSERT OR IGNORE INTO calls "
        "(request_id, session_id, agent, model, timestamp, input_tokens, output_tokens, "
        "cache_read_tokens, cache_write_5m_tokens, cache_write_1h_tokens) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            row["request_id"],
            row["session_id"],
            row.get("agent"),
            row["model"],
            row["timestamp"],
            row["input_tokens"],
            row["output_tokens"],
            row.get("cache_read_tokens", 0),
            row.get("cache_write_5m_tokens", 0),
            row.get("cache_write_1h_tokens", 0),
        ),
    )


def has_session(conn, session_id: str) -> bool:
    """True if any row for `session_id` is already recorded in `calls`."""
    row = conn.execute("SELECT 1 FROM calls WHERE session_id = ? LIMIT 1", (session_id,)).fetchone()
    return row is not None


def insert_usage_limit_event(conn, *, session_id, timestamp, raw_entry):
    conn.execute(
        "INSERT INTO usage_limit_events (session_id, timestamp, raw_entry) VALUES (?, ?, ?)",
        (session_id, timestamp, raw_entry),
    )


def insert_tool_use(conn, *, tool_use_id, request_id, session_id, agent, tool_name, timestamp, detail=None):
    conn.execute(
        "INSERT OR IGNORE INTO tool_uses "
        "(tool_use_id, request_id, session_id, agent, tool_name, detail, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (tool_use_id, request_id, session_id, agent, tool_name, detail, timestamp),
    )


def save_session_label(conn, *, session_id, label):
    """Upserts `label` for `session_id`, replacing whatever was stored
    before (a session's title can be revised - see parser.py's
    `_extract_ai_title`). Callers only invoke this when a title was
    actually found, so a session with no title this pass keeps its
    previously saved label rather than having it wiped.
    """
    conn.execute(
        "INSERT INTO session_labels (session_id, label, updated_at) "
        "VALUES (?, ?, CURRENT_TIMESTAMP) "
        "ON CONFLICT(session_id) DO UPDATE SET label = excluded.label, updated_at = excluded.updated_at",
        (session_id, label),
    )


def has_session_version(conn, session_id: str) -> bool:
    """True if a cairn version is already recorded for `session_id`."""
    row = conn.execute(
        "SELECT 1 FROM session_versions WHERE session_id = ? LIMIT 1", (session_id,)
    ).fetchone()
    return row is not None


def save_session_version(conn, *, session_id, version):
    """Records the cairn version `session_id` started under. The first
    value saved wins: a later call for the same session is ignored, so a
    session resumed after a plugin update keeps its start version.
    """
    conn.execute(
        "INSERT OR IGNORE INTO session_versions (session_id, cairn_version, recorded_at) "
        "VALUES (?, ?, CURRENT_TIMESTAMP)",
        (session_id, version),
    )
