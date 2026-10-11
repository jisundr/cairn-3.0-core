import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402
import parser  # noqa: E402


def write_jsonl(path: Path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for line in lines:
            if isinstance(line, str):
                f.write(line + "\n")
            else:
                f.write(json.dumps(line) + "\n")


def make_usage(**overrides):
    usage = dict(
        input_tokens=10,
        output_tokens=20,
        cache_read_input_tokens=5,
        cache_creation={"ephemeral_5m_input_tokens": 1, "ephemeral_1h_input_tokens": 2},
    )
    usage.update(overrides)
    return usage


def make_call_entry(request_id, tool_use_id=None, tool_name="Read",
                     timestamp="2026-08-28T00:00:00Z", model="claude-sonnet-5",
                     **usage_overrides):
    content = []
    if tool_use_id:
        content.append({"type": "tool_use", "id": tool_use_id, "name": tool_name, "input": {}})
    return {
        "type": "assistant",
        "requestId": request_id,
        "timestamp": timestamp,
        "message": {
            "role": "assistant",
            "model": model,
            "usage": make_usage(**usage_overrides),
            "content": content,
        },
    }


def make_dispatch_entry(tool_use_id, subagent_type, request_id="req-dispatch"):
    return {
        "type": "assistant",
        "requestId": request_id,
        "timestamp": "2026-08-28T00:00:00Z",
        "message": {
            "role": "assistant",
            "model": "claude-sonnet-5",
            "usage": make_usage(),
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_use_id,
                    "name": "Task",
                    "input": {"subagent_type": subagent_type, "description": "do work"},
                }
            ],
        },
    }


def make_dispatch_result_entry(tool_use_id, agent_id):
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": [{"type": "text", "text": f"Dispatched. agentId: {agent_id}"}],
                }
            ],
        },
    }


def test_build_agent_map_maps_subagent_type_to_agent_id():
    main_entries = [
        make_dispatch_entry("toolu_1", "builder"),
        make_dispatch_result_entry("toolu_1", "abc123def"),
    ]
    agent_map = parser.build_agent_map(main_entries)
    assert agent_map == {"abc123def": "builder"}


def test_build_agent_map_skips_unresolved_dispatch():
    main_entries = [make_dispatch_entry("toolu_1", "builder")]
    agent_map = parser.build_agent_map(main_entries)
    assert agent_map == {}


def test_parse_session_attributes_main_and_subagent_entries(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    transcript_path = tmp_path / "session.jsonl"

    write_jsonl(transcript_path, [
        make_dispatch_entry("toolu_dispatch", "builder"),
        make_dispatch_result_entry("toolu_dispatch", "abc123"),
        make_call_entry("req-main", tool_use_id="toolu_main", tool_name="Read"),
    ])
    write_jsonl(tmp_path / "session" / "subagents" / "agent-abc123.jsonl", [
        make_call_entry("req-sub", tool_use_id="toolu_sub", tool_name="Write"),
    ])

    parser.parse_session(cairn_dir, transcript_path, "sess-1")

    conn = db.connect(cairn_dir)
    calls = {row[0]: row[1] for row in conn.execute("SELECT request_id, agent FROM calls")}
    tool_uses = {row[0]: row[1] for row in conn.execute("SELECT tool_use_id, agent FROM tool_uses")}

    assert calls["req-main"] == "main"
    assert calls["req-sub"] == "builder"
    assert tool_uses["toolu_main"] == "main"
    assert tool_uses["toolu_sub"] == "builder"


def test_parse_session_tags_unmatched_subagent_as_unknown(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    transcript_path = tmp_path / "session.jsonl"

    write_jsonl(transcript_path, [
        make_call_entry("req-main", tool_use_id="toolu_main"),
    ])
    write_jsonl(tmp_path / "session" / "subagents" / "agent-zzz999.jsonl", [
        make_call_entry("req-sub", tool_use_id="toolu_sub"),
    ])

    parser.parse_session(cairn_dir, transcript_path, "sess-1")

    conn = db.connect(cairn_dir)
    agent = conn.execute("SELECT agent FROM calls WHERE request_id = 'req-sub'").fetchone()[0]
    assert agent == "unknown"


def test_parse_session_dedupes_duplicate_request_id(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    transcript_path = tmp_path / "session.jsonl"

    write_jsonl(transcript_path, [
        make_call_entry("req-dup", tool_use_id="toolu_1"),
        make_call_entry("req-dup", tool_use_id="toolu_2", output_tokens=999),
    ])

    parser.parse_session(cairn_dir, transcript_path, "sess-1")

    conn = db.connect(cairn_dir)
    rows = conn.execute("SELECT output_tokens FROM calls WHERE request_id = 'req-dup'").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == 20


def test_parse_session_dedupes_duplicate_tool_use_id(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    transcript_path = tmp_path / "session.jsonl"

    write_jsonl(transcript_path, [
        make_call_entry("req-1", tool_use_id="toolu_dup", tool_name="Read"),
        make_call_entry("req-2", tool_use_id="toolu_dup", tool_name="Write"),
    ])

    parser.parse_session(cairn_dir, transcript_path, "sess-1")

    conn = db.connect(cairn_dir)
    rows = conn.execute("SELECT tool_name FROM tool_uses WHERE tool_use_id = 'toolu_dup'").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "Read"


def test_genuine_usage_limit_string_message_routes_to_usage_limit_events(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    transcript_path = tmp_path / "session.jsonl"

    write_jsonl(transcript_path, [
        {
            "isApiErrorMessage": True,
            "timestamp": "2026-08-28T00:00:00Z",
            "message": "Claude usage limit reached|1735689600",
        },
    ])

    parser.parse_session(cairn_dir, transcript_path, "sess-1")

    conn = db.connect(cairn_dir)
    calls = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
    events = conn.execute("SELECT session_id FROM usage_limit_events").fetchall()
    assert calls == 0
    assert events == [("sess-1",)]


def test_generic_api_error_message_does_not_route_to_usage_limit_events(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    transcript_path = tmp_path / "session.jsonl"

    write_jsonl(transcript_path, [
        {
            "isApiErrorMessage": True,
            "timestamp": "2026-08-28T00:00:00Z",
            "message": {
                "model": "<synthetic>",
                "role": "assistant",
                "content": [{"type": "text", "text": "error occurred"}],
            },
            "error": "server_error",
        },
    ])

    parser.parse_session(cairn_dir, transcript_path, "sess-1")

    conn = db.connect(cairn_dir)
    calls = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
    events = conn.execute("SELECT session_id FROM usage_limit_events").fetchall()
    assert calls == 0
    assert events == []


def test_malformed_json_line_does_not_block_surrounding_entries(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    transcript_path = tmp_path / "session.jsonl"

    write_jsonl(transcript_path, [
        make_call_entry("req-1", tool_use_id="toolu_1"),
        "{not valid json",
        make_call_entry("req-2", tool_use_id="toolu_2"),
    ])

    parser.parse_session(cairn_dir, transcript_path, "sess-1")

    conn = db.connect(cairn_dir)
    request_ids = {row[0] for row in conn.execute("SELECT request_id FROM calls")}
    assert request_ids == {"req-1", "req-2"}


def test_extract_ai_title_keeps_last_non_empty_occurrence():
    entries = [
        {"type": "ai-title", "aiTitle": "First draft title"},
        make_call_entry("req-1", tool_use_id="toolu_1"),
        {"type": "ai-title", "aiTitle": "Revised title"},
    ]
    assert parser._extract_ai_title(entries) == "Revised title"


def test_extract_ai_title_returns_none_when_absent():
    entries = [make_call_entry("req-1", tool_use_id="toolu_1")]
    assert parser._extract_ai_title(entries) is None


def test_extract_ai_title_ignores_a_later_empty_title():
    entries = [
        {"type": "ai-title", "aiTitle": "Keep this one"},
        {"type": "ai-title", "aiTitle": ""},
    ]
    assert parser._extract_ai_title(entries) == "Keep this one"


def test_parse_session_returns_last_ai_title_and_saves_it(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    transcript_path = tmp_path / "session.jsonl"

    write_jsonl(transcript_path, [
        {"type": "ai-title", "aiTitle": "First draft title"},
        make_call_entry("req-1", tool_use_id="toolu_1"),
        {"type": "ai-title", "aiTitle": "Revised title"},
    ])

    title = parser.parse_session(cairn_dir, transcript_path, "sess-1")
    assert title == "Revised title"

    conn = db.connect(cairn_dir)
    row = conn.execute("SELECT label FROM session_labels WHERE session_id = 'sess-1'").fetchone()
    assert row == ("Revised title",)


def test_parse_session_returns_none_and_skips_save_when_no_title_found(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    transcript_path = tmp_path / "session.jsonl"

    write_jsonl(transcript_path, [
        make_call_entry("req-1", tool_use_id="toolu_1"),
    ])

    title = parser.parse_session(cairn_dir, transcript_path, "sess-1")
    assert title is None

    conn = db.connect(cairn_dir)
    row = conn.execute("SELECT label FROM session_labels WHERE session_id = 'sess-1'").fetchone()
    assert row is None


def test_parse_session_rerun_without_a_title_does_not_wipe_a_previously_saved_one(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    transcript_path = tmp_path / "session.jsonl"

    write_jsonl(transcript_path, [
        {"type": "ai-title", "aiTitle": "Saved on first pass"},
        make_call_entry("req-1", tool_use_id="toolu_1"),
    ])
    parser.parse_session(cairn_dir, transcript_path, "sess-1")

    # A later pass over a transcript that (for whatever reason) carries no
    # ai-title record this time must not clear the label already saved.
    write_jsonl(transcript_path, [
        make_call_entry("req-1", tool_use_id="toolu_1"),
    ])
    title = parser.parse_session(cairn_dir, transcript_path, "sess-1")
    assert title is None

    conn = db.connect(cairn_dir)
    row = conn.execute("SELECT label FROM session_labels WHERE session_id = 'sess-1'").fetchone()
    assert row == ("Saved on first pass",)


def test_parse_session_is_idempotent_on_rerun(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    transcript_path = tmp_path / "session.jsonl"

    write_jsonl(transcript_path, [
        make_call_entry("req-1", tool_use_id="toolu_1"),
    ])

    parser.parse_session(cairn_dir, transcript_path, "sess-1")
    conn = db.connect(cairn_dir)
    first_calls = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
    first_tool_uses = conn.execute("SELECT COUNT(*) FROM tool_uses").fetchone()[0]

    parser.parse_session(cairn_dir, transcript_path, "sess-1")
    second_calls = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
    second_tool_uses = conn.execute("SELECT COUNT(*) FROM tool_uses").fetchone()[0]

    assert first_calls == second_calls == 1
    assert first_tool_uses == second_tool_uses == 1


def test_parse_transcript_sentinels_a_missing_model_instead_of_crashing(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    transcript_path = tmp_path / "session.jsonl"

    write_jsonl(transcript_path, [
        make_call_entry("req-1", tool_use_id="toolu_1", model=None),
    ])

    # calls.model is NOT NULL - this must not raise sqlite3.IntegrityError.
    parser.parse_session(cairn_dir, transcript_path, "sess-1")

    conn = db.connect(cairn_dir)
    row = conn.execute(
        "SELECT model, input_tokens, output_tokens FROM calls WHERE request_id = 'req-1'"
    ).fetchone()
    assert row == (parser.UNKNOWN_MODEL, 10, 20)


def test_parse_transcript_sentinels_an_absent_model_key_instead_of_crashing(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    transcript_path = tmp_path / "session.jsonl"
    entry = make_call_entry("req-1", tool_use_id="toolu_1")
    del entry["message"]["model"]
    write_jsonl(transcript_path, [entry])

    parser.parse_session(cairn_dir, transcript_path, "sess-1")

    conn = db.connect(cairn_dir)
    model = conn.execute("SELECT model FROM calls WHERE request_id = 'req-1'").fetchone()[0]
    assert model == parser.UNKNOWN_MODEL


def _write_sessions_log(cairn_dir: Path, lines):
    cairn_dir.mkdir(parents=True, exist_ok=True)
    (cairn_dir / "sessions.log").write_text("".join(line + "\n" for line in lines))


def _stored_version(cairn_dir: Path, session_id: str):
    conn = db.connect(cairn_dir)
    try:
        row = conn.execute(
            "SELECT cairn_version FROM session_versions WHERE session_id = ?", (session_id,)
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _parse_with_log(tmp_path, log_lines, session_id="sess-1"):
    cairn_dir = tmp_path / ".cairn"
    if log_lines is not None:
        _write_sessions_log(cairn_dir, log_lines)
    transcript_path = tmp_path / "session.jsonl"
    write_jsonl(transcript_path, [make_call_entry("req-1")])
    parser.parse_session(cairn_dir, transcript_path, session_id)
    return cairn_dir


def test_parse_session_stores_the_cairn_version_from_sessions_log(tmp_path):
    cairn_dir = _parse_with_log(tmp_path, [
        "2026-09-30T00:00:00Z\t0.39.5\tsess-other",
        "2026-09-30T00:01:00Z\t0.40.0\tsess-1",
    ])

    assert _stored_version(cairn_dir, "sess-1") == "0.40.0"


def test_parse_session_accepts_a_prerelease_suffix(tmp_path):
    cairn_dir = _parse_with_log(tmp_path, ["2026-09-30T00:00:00Z\t1.2.3-rc.1\tsess-1"])

    assert _stored_version(cairn_dir, "sess-1") == "1.2.3-rc.1"


def test_parse_session_ignores_unknown_malformed_and_other_sessions_versions(tmp_path):
    cairn_dir = _parse_with_log(tmp_path, [
        "2026-09-30T00:00:00Z\tunknown\tsess-1",
        "2026-09-30T00:00:01Z\t<script>alert(1)</script>\tsess-1",
        "2026-09-30T00:00:02Z\t1.2\tsess-1",
        "2026-09-30T00:00:03Z\t1.2.3-" + "a" * 60 + "\tsess-1",
        "2026-09-30T00:00:04Z\t0.40.0\tsess-1\textra",
        "2026-09-30T00:00:05Z\t0.40.0",
        "2026-09-30T00:00:06Z\t0.40.0\tsess-other",
    ])

    assert _stored_version(cairn_dir, "sess-1") is None


def test_parse_session_without_a_sessions_log_stores_no_version(tmp_path):
    cairn_dir = _parse_with_log(tmp_path, None)

    assert _stored_version(cairn_dir, "sess-1") is None
    conn = db.connect(cairn_dir)
    assert conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 1


def test_parse_session_with_an_undecodable_sessions_log_still_parses(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    cairn_dir.mkdir(parents=True)
    (cairn_dir / "sessions.log").write_bytes(b"\xff\xfe\t0.40.0\tsess-1\n")
    transcript_path = tmp_path / "session.jsonl"
    write_jsonl(transcript_path, [make_call_entry("req-1")])

    parser.parse_session(cairn_dir, transcript_path, "sess-1")

    assert _stored_version(cairn_dir, "sess-1") is None
    conn = db.connect(cairn_dir)
    assert conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 1


def test_parse_session_keeps_the_first_version_after_a_later_update(tmp_path):
    cairn_dir = _parse_with_log(tmp_path, ["2026-09-30T00:00:00Z\t0.39.5\tsess-1"])
    with (cairn_dir / "sessions.log").open("a") as f:
        f.write("2026-09-30T01:00:00Z\t0.40.0\tsess-1\n")
    parser.parse_session(cairn_dir, tmp_path / "session.jsonl", "sess-1")

    assert _stored_version(cairn_dir, "sess-1") == "0.39.5"


def test_parse_session_takes_the_first_valid_line_over_an_earlier_unknown(tmp_path):
    cairn_dir = _parse_with_log(tmp_path, [
        "2026-09-30T00:00:00Z\tunknown\tsess-1",
        "2026-09-30T00:05:00Z\t0.40.0\tsess-1",
        "2026-09-30T00:09:00Z\t0.41.0\tsess-1",
    ])

    assert _stored_version(cairn_dir, "sess-1") == "0.40.0"


def test_parse_session_picks_up_a_version_logged_after_an_earlier_parse(tmp_path):
    cairn_dir = _parse_with_log(tmp_path, [])
    assert _stored_version(cairn_dir, "sess-1") is None

    _write_sessions_log(cairn_dir, ["2026-09-30T00:00:00Z\t0.40.0\tsess-1"])
    parser.parse_session(cairn_dir, tmp_path / "session.jsonl", "sess-1")

    assert _stored_version(cairn_dir, "sess-1") == "0.40.0"


def test_parse_session_ignores_a_version_written_in_non_ascii_digits(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    cairn_dir.mkdir(parents=True)
    (cairn_dir / "sessions.log").write_text(
        "2026-09-30T00:00:00Z\t٠.٤٠.٠\tsess-1\n", encoding="utf-8"
    )
    transcript_path = tmp_path / "session.jsonl"
    write_jsonl(transcript_path, [make_call_entry("req-1")])

    parser.parse_session(cairn_dir, transcript_path, "sess-1")

    assert _stored_version(cairn_dir, "sess-1") is None


def test_parse_session_keeps_token_rows_when_the_version_step_fails(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(db, "save_session_version", fail)

    cairn_dir = _parse_with_log(tmp_path, ["2026-09-30T00:00:00Z\t0.40.0\tsess-1"])

    assert _stored_version(cairn_dir, "sess-1") is None
    conn = db.connect(cairn_dir)
    try:
        assert conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 1
    finally:
        conn.close()


def test_a_later_parse_stores_the_version_after_an_earlier_version_step_failed(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(db, "save_session_version", fail)
    cairn_dir = _parse_with_log(tmp_path, ["2026-09-30T00:00:00Z\t0.40.0\tsess-1"])
    assert _stored_version(cairn_dir, "sess-1") is None

    monkeypatch.undo()
    parser.parse_session(cairn_dir, tmp_path / "session.jsonl", "sess-1")

    assert _stored_version(cairn_dir, "sess-1") == "0.40.0"
    conn = db.connect(cairn_dir)
    try:
        # The second pass re-reads the same transcript; its call is not duplicated.
        assert conn.execute("SELECT session_id, COUNT(*) FROM calls GROUP BY session_id").fetchall() == [("sess-1", 1)]
    finally:
        conn.close()


class _RollbackFails:
    """Wraps a real connection so only rollback() raises, as on a disk I/O error."""

    def __init__(self, conn):
        self._conn = conn

    def rollback(self):
        raise sqlite3.OperationalError("disk I/O error")

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_parse_session_survives_a_failing_rollback_after_the_version_step_fails(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    real_connect = db.connect
    monkeypatch.setattr(db, "save_session_version", fail)
    monkeypatch.setattr(db, "connect", lambda cairn_dir: _RollbackFails(real_connect(cairn_dir)))

    cairn_dir = _parse_with_log(tmp_path, ["2026-09-30T00:00:00Z\t0.40.0\tsess-1"])

    monkeypatch.undo()
    assert _stored_version(cairn_dir, "sess-1") is None
    conn = db.connect(cairn_dir)
    try:
        assert conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 1
    finally:
        conn.close()
