import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backfill  # noqa: E402
import db  # noqa: E402
import parser  # noqa: E402
import server  # noqa: E402

from test_parser import make_call_entry, write_jsonl  # noqa: E402


def _transcript_dir(claude_projects_dir: Path, project_root: Path) -> Path:
    return claude_projects_dir / server.encode_project_path(project_root)


def _write_session(claude_projects_dir: Path, project_root: Path, session_id: str, *, request_id=None):
    entries = [make_call_entry(request_id or f"req-{session_id}")]
    path = _transcript_dir(claude_projects_dir, project_root) / f"{session_id}.jsonl"
    write_jsonl(path, entries)
    return path


def _session_ids(cairn_dir: Path) -> set[str]:
    conn = db.connect(cairn_dir)
    try:
        rows = conn.execute("SELECT DISTINCT session_id FROM calls").fetchall()
        return {row[0] for row in rows}
    finally:
        conn.close()


def test_local_only_run_ingests_launching_project(tmp_path):
    claude_projects_dir = tmp_path / "claude-projects"
    local_project = tmp_path / "local"
    local_project.mkdir()
    _write_session(claude_projects_dir, local_project, "sess-local")

    backfill.run(known_projects=[], local_project=local_project, claude_projects_dir=claude_projects_dir)

    assert _session_ids(local_project / ".cairn") == {"sess-local"}


def test_local_and_known_project_each_land_only_in_their_own_db(tmp_path):
    claude_projects_dir = tmp_path / "claude-projects"
    local_project = tmp_path / "local"
    other_project = tmp_path / "other"
    local_project.mkdir()
    other_project.mkdir()
    _write_session(claude_projects_dir, local_project, "sess-local")
    _write_session(claude_projects_dir, other_project, "sess-other")

    backfill.run(
        known_projects=[other_project],
        local_project=local_project,
        claude_projects_dir=claude_projects_dir,
    )

    # Write-scope isolation: each project's own tokens.db has only its own
    # session - never the other project's row, in either direction.
    assert _session_ids(local_project / ".cairn") == {"sess-local"}
    assert _session_ids(other_project / ".cairn") == {"sess-other"}


def test_run_never_writes_known_projects_json(tmp_path):
    claude_projects_dir = tmp_path / "claude-projects"
    local_project = tmp_path / "local"
    other_project = tmp_path / "other"
    local_project.mkdir()
    other_project.mkdir()
    _write_session(claude_projects_dir, local_project, "sess-local")
    _write_session(claude_projects_dir, other_project, "sess-other")

    known_projects_path = tmp_path / "known-projects.json"
    payload = json.dumps([str(other_project)])
    known_projects_path.write_text(payload)
    before = known_projects_path.read_bytes()

    # run() only ever receives resolved Paths - it never opens this file.
    backfill.run(
        known_projects=[other_project],
        local_project=local_project,
        claude_projects_dir=claude_projects_dir,
    )

    assert known_projects_path.read_bytes() == before


def test_second_run_is_a_noop_for_already_ingested_sessions(tmp_path, monkeypatch):
    claude_projects_dir = tmp_path / "claude-projects"
    local_project = tmp_path / "local"
    local_project.mkdir()
    _write_session(claude_projects_dir, local_project, "sess-local")

    backfill.run(known_projects=[], local_project=local_project, claude_projects_dir=claude_projects_dir)
    assert _session_ids(local_project / ".cairn") == {"sess-local"}

    calls = []
    real_parse_session = parser.parse_session

    def spy_parse_session(cairn_dir, transcript_path, session_id):
        calls.append(session_id)
        return real_parse_session(cairn_dir, transcript_path, session_id)

    monkeypatch.setattr(parser, "parse_session", spy_parse_session)

    backfill.run(known_projects=[], local_project=local_project, claude_projects_dir=claude_projects_dir)

    assert calls == []
    assert _session_ids(local_project / ".cairn") == {"sess-local"}


def test_one_project_with_no_transcript_dir_does_not_abort_the_rest(tmp_path):
    claude_projects_dir = tmp_path / "claude-projects"
    local_project = tmp_path / "local"
    broken_project = tmp_path / "broken"
    healthy_project = tmp_path / "healthy"
    local_project.mkdir()
    broken_project.mkdir()
    healthy_project.mkdir()
    _write_session(claude_projects_dir, local_project, "sess-local")
    _write_session(claude_projects_dir, healthy_project, "sess-healthy")
    # broken_project has no transcript directory under claude_projects_dir at all.

    backfill.run(
        known_projects=[broken_project, healthy_project],
        local_project=local_project,
        claude_projects_dir=claude_projects_dir,
    )

    assert _session_ids(local_project / ".cairn") == {"sess-local"}
    assert _session_ids(healthy_project / ".cairn") == {"sess-healthy"}
    assert not (broken_project / ".cairn" / "tokens.db").exists()


def test_a_root_that_raises_mid_processing_does_not_abort_other_roots(tmp_path, monkeypatch):
    # Distinct from the missing-transcript-dir case above (which returns
    # early before the per-root try/except body ever runs a risky
    # operation) - this exercises the try/except itself by making a real
    # exception happen partway through one root's processing.
    claude_projects_dir = tmp_path / "claude-projects"
    local_project = tmp_path / "local"
    broken_project = tmp_path / "broken"
    healthy_project = tmp_path / "healthy"
    local_project.mkdir()
    broken_project.mkdir()
    healthy_project.mkdir()
    _write_session(claude_projects_dir, local_project, "sess-local")
    _write_session(claude_projects_dir, broken_project, "sess-broken")
    _write_session(claude_projects_dir, healthy_project, "sess-healthy")

    real_connect = db.connect

    def flaky_connect(cairn_dir):
        if cairn_dir == broken_project / ".cairn":
            raise OSError("simulated unreadable project")
        return real_connect(cairn_dir)

    monkeypatch.setattr(db, "connect", flaky_connect)

    backfill.run(
        known_projects=[broken_project, healthy_project],
        local_project=local_project,
        claude_projects_dir=claude_projects_dir,
    )

    assert _session_ids(local_project / ".cairn") == {"sess-local"}
    assert _session_ids(healthy_project / ".cairn") == {"sess-healthy"}


def test_one_malformed_session_does_not_abort_sibling_sessions(tmp_path, monkeypatch):
    claude_projects_dir = tmp_path / "claude-projects"
    local_project = tmp_path / "local"
    local_project.mkdir()
    _write_session(claude_projects_dir, local_project, "sess-bad")
    _write_session(claude_projects_dir, local_project, "sess-good")

    real_parse_session = parser.parse_session

    def flaky_parse_session(cairn_dir, transcript_path, session_id):
        if session_id == "sess-bad":
            raise ValueError("simulated malformed transcript")
        return real_parse_session(cairn_dir, transcript_path, session_id)

    monkeypatch.setattr(parser, "parse_session", flaky_parse_session)

    backfill.run(known_projects=[], local_project=local_project, claude_projects_dir=claude_projects_dir)

    assert _session_ids(local_project / ".cairn") == {"sess-good"}


def test_local_project_also_listed_in_known_projects_is_processed_once(tmp_path):
    claude_projects_dir = tmp_path / "claude-projects"
    local_project = tmp_path / "local"
    local_project.mkdir()
    _write_session(claude_projects_dir, local_project, "sess-local")

    # Should not raise, and should not duplicate-insert or double-process.
    backfill.run(
        known_projects=[local_project],
        local_project=local_project,
        claude_projects_dir=claude_projects_dir,
    )

    assert _session_ids(local_project / ".cairn") == {"sess-local"}
