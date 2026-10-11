import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402


def make_row(**overrides):
    row = dict(
        request_id="req-1",
        session_id="sess-1",
        agent="main",
        model="claude-sonnet-5",
        timestamp="2026-08-28T00:00:00Z",
        input_tokens=2,
        output_tokens=498,
        cache_read_tokens=0,
        cache_write_5m_tokens=0,
        cache_write_1h_tokens=85386,
    )
    row.update(overrides)
    return row


def make_tool_use(**overrides):
    tool_use = dict(
        tool_use_id="toolu-1",
        request_id="req-1",
        session_id="sess-1",
        agent="main",
        tool_name="Read",
        timestamp="2026-08-28T00:00:00Z",
        detail=None,
    )
    tool_use.update(overrides)
    return tool_use


def test_connect_creates_db_file_and_tables(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    conn = db.connect(cairn_dir)
    assert db.db_path(cairn_dir).exists()

    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "calls" in tables
    assert "usage_limit_events" in tables
    assert "tool_uses" in tables
    assert "session_labels" in tables
    assert "session_versions" in tables


def test_connect_creates_expected_indexes(tmp_path):
    conn = db.connect(tmp_path / ".cairn")

    indexes = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }
    assert "idx_calls_session_id" in indexes
    assert "idx_calls_timestamp_trunc" in indexes
    assert "idx_tool_uses_session_id" in indexes
    assert "idx_usage_limit_events_session_id" in indexes


def test_connect_is_idempotent_across_calls(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    conn1 = db.connect(cairn_dir)
    db.insert_call(conn1, make_row())
    conn1.commit()
    conn1.close()

    conn2 = db.connect(cairn_dir)
    row = conn2.execute("SELECT request_id FROM calls").fetchone()
    assert row == ("req-1",)

    indexes = [
        row[0]
        for row in conn2.execute("SELECT name FROM sqlite_master WHERE type='index'")
    ]
    assert indexes.count("idx_calls_session_id") == 1
    assert indexes.count("idx_calls_timestamp_trunc") == 1
    assert indexes.count("idx_tool_uses_session_id") == 1
    assert indexes.count("idx_usage_limit_events_session_id") == 1


def test_insert_call_round_trips_fields(tmp_path):
    conn = db.connect(tmp_path / ".cairn")
    db.insert_call(conn, make_row())
    conn.commit()

    row = conn.execute("SELECT * FROM calls WHERE request_id = 'req-1'").fetchone()
    assert row is not None
    columns = [d[0] for d in conn.execute("SELECT * FROM calls").description]
    record = dict(zip(columns, row))
    assert record["agent"] == "main"
    assert record["model"] == "claude-sonnet-5"
    assert record["output_tokens"] == 498
    assert record["cache_write_1h_tokens"] == 85386


def test_insert_call_dedupes_on_request_id(tmp_path):
    conn = db.connect(tmp_path / ".cairn")
    db.insert_call(conn, make_row())
    db.insert_call(conn, make_row(output_tokens=999))
    conn.commit()

    rows = conn.execute("SELECT output_tokens FROM calls WHERE request_id = 'req-1'").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == 498


def test_insert_call_defaults_optional_cache_fields(tmp_path):
    conn = db.connect(tmp_path / ".cairn")
    db.insert_call(
        conn,
        {
            "request_id": "req-2",
            "session_id": "sess-1",
            "agent": "unknown",
            "model": "claude-sonnet-5",
            "timestamp": "2026-08-28T00:00:00Z",
            "input_tokens": 1,
            "output_tokens": 1,
        },
    )
    conn.commit()

    row = conn.execute(
        "SELECT cache_read_tokens, cache_write_5m_tokens, cache_write_1h_tokens "
        "FROM calls WHERE request_id = 'req-2'"
    ).fetchone()
    assert row == (0, 0, 0)


def test_insert_call_defaults_agent_when_absent(tmp_path):
    conn = db.connect(tmp_path / ".cairn")
    row = make_row()
    del row["agent"]
    db.insert_call(conn, row)
    conn.commit()

    agent = conn.execute("SELECT agent FROM calls WHERE request_id = 'req-1'").fetchone()[0]
    assert agent is None


def test_insert_usage_limit_event(tmp_path):
    conn = db.connect(tmp_path / ".cairn")
    db.insert_usage_limit_event(
        conn,
        session_id="sess-1",
        timestamp="2026-08-28T00:00:00Z",
        raw_entry='{"isApiErrorMessage": true}',
    )
    conn.commit()

    row = conn.execute("SELECT session_id, raw_entry FROM usage_limit_events").fetchone()
    assert row == ("sess-1", '{"isApiErrorMessage": true}')


def test_insert_tool_use_round_trips_fields(tmp_path):
    conn = db.connect(tmp_path / ".cairn")
    db.insert_tool_use(conn, **make_tool_use(detail=None))
    conn.commit()

    row = conn.execute("SELECT * FROM tool_uses WHERE tool_use_id = 'toolu-1'").fetchone()
    assert row is not None
    columns = [d[0] for d in conn.execute("SELECT * FROM tool_uses").description]
    record = dict(zip(columns, row))
    assert record["request_id"] == "req-1"
    assert record["agent"] == "main"
    assert record["tool_name"] == "Read"
    assert record["detail"] is None


def test_insert_tool_use_round_trips_non_null_detail(tmp_path):
    conn = db.connect(tmp_path / ".cairn")
    db.insert_tool_use(conn, **make_tool_use(
        tool_use_id="toolu-2", tool_name="Skill", detail="cairn:start",
    ))
    conn.commit()

    row = conn.execute(
        "SELECT detail FROM tool_uses WHERE tool_use_id = 'toolu-2'"
    ).fetchone()
    assert row == ("cairn:start",)


def test_insert_tool_use_dedupes_on_tool_use_id(tmp_path):
    conn = db.connect(tmp_path / ".cairn")
    db.insert_tool_use(conn, **make_tool_use())
    db.insert_tool_use(conn, **make_tool_use(tool_name="Write"))
    conn.commit()

    rows = conn.execute(
        "SELECT tool_name FROM tool_uses WHERE tool_use_id = 'toolu-1'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "Read"


def test_save_session_label_round_trips(tmp_path):
    conn = db.connect(tmp_path / ".cairn")
    db.save_session_label(conn, session_id="sess-1", label="Add a login page")
    conn.commit()

    row = conn.execute("SELECT label FROM session_labels WHERE session_id = 'sess-1'").fetchone()
    assert row == ("Add a login page",)


def test_save_session_label_replaces_existing_label_for_same_session_id(tmp_path):
    conn = db.connect(tmp_path / ".cairn")
    db.save_session_label(conn, session_id="sess-1", label="First title")
    db.save_session_label(conn, session_id="sess-1", label="Revised title")
    conn.commit()

    rows = conn.execute("SELECT label FROM session_labels WHERE session_id = 'sess-1'").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "Revised title"


def test_save_session_label_keys_by_session_id_independently(tmp_path):
    conn = db.connect(tmp_path / ".cairn")
    db.save_session_label(conn, session_id="sess-1", label="Session one")
    db.save_session_label(conn, session_id="sess-2", label="Session two")
    conn.commit()

    rows = {
        row[0]: row[1]
        for row in conn.execute("SELECT session_id, label FROM session_labels")
    }
    assert rows == {"sess-1": "Session one", "sess-2": "Session two"}


def test_has_session_true_when_a_row_exists(tmp_path):
    conn = db.connect(tmp_path / ".cairn")
    db.insert_call(conn, make_row(session_id="sess-present"))
    conn.commit()

    assert db.has_session(conn, "sess-present") is True


def test_has_session_false_when_absent(tmp_path):
    conn = db.connect(tmp_path / ".cairn")

    assert db.has_session(conn, "sess-missing") is False


def test_connect_sets_wal_journal_mode(tmp_path):
    conn = db.connect(tmp_path / ".cairn")

    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_wal_write_does_not_block_a_concurrent_reader(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    writer = db.connect(cairn_dir)
    reader = db.connect(cairn_dir)

    # A reader holding an open cursor shouldn't block a writer's commit
    # under WAL mode (the minimum guarantee the fix provides).
    cursor = reader.execute("SELECT * FROM calls")
    db.insert_call(writer, make_row())
    writer.commit()
    cursor.fetchall()

    row = reader.execute("SELECT request_id FROM calls").fetchone()
    assert row == ("req-1",)


def test_connect_sets_schema_version_pragma(tmp_path):
    conn = db.connect(tmp_path / ".cairn")

    version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == db.SCHEMA_VERSION


def test_connect_migrates_a_pre_marker_database_without_crashing(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    cairn_dir.mkdir(parents=True)
    path = db.db_path(cairn_dir)

    # Simulate a tokens.db written before the schema-version marker
    # existed: same table DDL, but PRAGMA user_version never set (so it
    # defaults to 0), with one row already in it.
    legacy = sqlite3.connect(path)
    legacy.execute(db.CALLS_SCHEMA)
    legacy.execute(db.USAGE_LIMIT_EVENTS_SCHEMA)
    legacy.execute(db.TOOL_USES_SCHEMA)
    legacy.execute(db.SESSION_LABELS_SCHEMA)
    legacy.execute(
        "INSERT INTO calls (request_id, session_id, agent, model, timestamp, "
        "input_tokens, output_tokens) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("req-legacy", "sess-1", "main", "claude-sonnet-5", "2026-08-28T00:00:00Z", 1, 1),
    )
    legacy.commit()
    legacy.close()

    conn = db.connect(cairn_dir)

    row = conn.execute("SELECT request_id FROM calls WHERE request_id = 'req-legacy'").fetchone()
    assert row == ("req-legacy",)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == db.SCHEMA_VERSION


def _write_v1_database(cairn_dir):
    """A tokens.db as schema version 1 left it: the four original tables,
    user_version stamped 1, rows already in `calls` and `session_labels`,
    and no `session_versions` table."""
    cairn_dir.mkdir(parents=True)
    legacy = sqlite3.connect(db.db_path(cairn_dir))
    legacy.execute(db.CALLS_SCHEMA)
    legacy.execute(db.USAGE_LIMIT_EVENTS_SCHEMA)
    legacy.execute(db.TOOL_USES_SCHEMA)
    legacy.execute(db.SESSION_LABELS_SCHEMA)
    for i in range(3):
        legacy.execute(
            "INSERT INTO calls (request_id, session_id, agent, model, timestamp, "
            "input_tokens, output_tokens) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"req-v1-{i}", "sess-v1", "main", "claude-sonnet-5", "2026-08-28T00:00:00Z", 1, 1),
        )
    legacy.execute(
        "INSERT INTO session_labels (session_id, label, updated_at) VALUES (?, ?, ?)",
        ("sess-v1", "Old title", "2026-08-28 00:00:00"),
    )
    legacy.execute("PRAGMA user_version = 1")
    legacy.commit()
    legacy.close()


def test_connect_migrates_a_v1_database_keeping_every_row(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    _write_v1_database(cairn_dir)

    conn = db.connect(cairn_dir)

    rows = conn.execute("SELECT request_id FROM calls ORDER BY request_id").fetchall()
    assert rows == [("req-v1-0",), ("req-v1-1",), ("req-v1-2",)]
    label = conn.execute("SELECT label FROM session_labels WHERE session_id = 'sess-v1'").fetchone()
    assert label == ("Old title",)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "session_versions" in tables
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    assert db.has_session_version(conn, "sess-v1") is False


def test_connect_twice_on_a_migrated_database_changes_nothing(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    _write_v1_database(cairn_dir)
    first = db.connect(cairn_dir)
    db.save_session_version(first, session_id="sess-v1", version="0.40.0")
    first.commit()
    first.close()

    second = db.connect(cairn_dir)

    assert second.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 3
    assert second.execute(
        "SELECT cairn_version FROM session_versions WHERE session_id = 'sess-v1'"
    ).fetchone() == ("0.40.0",)
    tables = [r[0] for r in second.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    assert tables.count("session_versions") == 1
    assert second.execute("PRAGMA user_version").fetchone()[0] == 2


def test_save_session_version_round_trips(tmp_path):
    conn = db.connect(tmp_path / ".cairn")
    assert db.has_session_version(conn, "sess-1") is False

    db.save_session_version(conn, session_id="sess-1", version="0.40.0")

    assert db.has_session_version(conn, "sess-1") is True
    row = conn.execute(
        "SELECT cairn_version, recorded_at FROM session_versions WHERE session_id = 'sess-1'"
    ).fetchone()
    assert row[0] == "0.40.0"
    assert row[1]


def test_save_session_version_keeps_the_first_value(tmp_path):
    conn = db.connect(tmp_path / ".cairn")

    db.save_session_version(conn, session_id="sess-1", version="0.39.5")
    db.save_session_version(conn, session_id="sess-1", version="0.40.0")

    rows = conn.execute("SELECT cairn_version FROM session_versions WHERE session_id = 'sess-1'").fetchall()
    assert rows == [("0.39.5",)]
