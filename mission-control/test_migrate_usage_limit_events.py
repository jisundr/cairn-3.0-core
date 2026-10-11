import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402
import migrate_usage_limit_events as migrate  # noqa: E402


def _insert_event(cairn_dir: Path, *, raw_entry: str, session_id="sess-1", timestamp="2026-08-28T00:00:00Z"):
    conn = db.connect(cairn_dir)
    try:
        db.insert_usage_limit_event(conn, session_id=session_id, timestamp=timestamp, raw_entry=raw_entry)
        conn.commit()
    finally:
        conn.close()


def test_is_genuine_usage_limit_entry_true_for_real_notice():
    raw = json.dumps({
        "isApiErrorMessage": True,
        "message": "Claude usage limit reached|1735689600",
    })
    assert migrate.is_genuine_usage_limit_entry(raw) is True


def test_is_genuine_usage_limit_entry_false_for_synthetic_assistant_turn():
    raw = json.dumps({
        "isApiErrorMessage": True,
        "message": {"model": "<synthetic>", "role": "assistant", "content": []},
        "error": "server_error",
    })
    assert migrate.is_genuine_usage_limit_entry(raw) is False


def test_is_genuine_usage_limit_entry_false_for_invalid_json():
    assert migrate.is_genuine_usage_limit_entry("{not valid json") is False


def test_migrate_project_deletes_false_positives_and_keeps_genuine_rows(tmp_path):
    cairn_dir = tmp_path / ".cairn"
    _insert_event(cairn_dir, raw_entry=json.dumps({
        "isApiErrorMessage": True,
        "message": "Claude usage limit reached|1735689600",
    }))
    _insert_event(cairn_dir, raw_entry=json.dumps({
        "isApiErrorMessage": True,
        "message": {"model": "<synthetic>", "role": "assistant"},
        "error": "model_not_found",
    }))
    _insert_event(cairn_dir, raw_entry="{not valid json")

    counts = migrate.migrate_project(cairn_dir)

    assert counts == {"checked": 3, "deleted": 2, "kept": 1}
    conn = db.connect(cairn_dir)
    try:
        remaining = conn.execute("SELECT raw_entry FROM usage_limit_events").fetchall()
    finally:
        conn.close()
    assert len(remaining) == 1
    assert json.loads(remaining[0][0])["message"].startswith("Claude usage limit reached")


def test_run_skips_projects_without_a_tokens_db(tmp_path):
    project_with_db = tmp_path / "with-db"
    project_without_db = tmp_path / "without-db"
    project_with_db.mkdir()
    project_without_db.mkdir()
    _insert_event(project_with_db / ".cairn", raw_entry=json.dumps({
        "isApiErrorMessage": True,
        "message": {"model": "<synthetic>"},
        "error": "server_error",
    }))

    results = migrate.run([project_with_db, project_without_db])

    assert set(results.keys()) == {project_with_db.resolve()}
    assert results[project_with_db.resolve()] == {"checked": 1, "deleted": 1, "kept": 0}


def test_run_deduplicates_equivalent_roots(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    _insert_event(project / ".cairn", raw_entry=json.dumps({
        "isApiErrorMessage": True,
        "message": "Claude usage limit reached|1735689600",
    }))

    results = migrate.run([project, project])

    assert len(results) == 1
