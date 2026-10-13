"""tasks-export.py: output pinned to state_schema.py parsing and to
mission-control/tasks.py column precedence, plus the ledger merge."""
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "mission-control"))
import state_schema  # noqa: E402
import tasks as mc_tasks  # noqa: E402

SCRIPT = ROOT / "plugin/skills/task-assets/assets/tasks-export.py"
spec = importlib.util.spec_from_file_location("tasks_export", SCRIPT)
te = importlib.util.module_from_spec(spec)
spec.loader.exec_module(te)

T = "docs/tasks/"


def state(goal="g", key_info="k", log=""):
    return f"---\nschema: 1\ngoal: {goal}\nkey_info: {key_info}\n---\n{log}"


def put(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


@pytest.fixture
def proj(tmp_path):
    r = tmp_path / "proj"
    (r / ".cairn").mkdir(parents=True)
    f = T + "2026-10-01-0900-build-feature/"
    put(r, f + "STATE.md", state("Feature", "approved, start step 1", "2026-10-02 08:30: planned\n- 2026-10-03 10:15 note\n"))
    put(r, f + "PLAN.md", "# plan\n")
    g = T + "2026-10-02-0900-build-building/"
    put(r, g + "STATE.md", state("Building", "step 2 of 4 in progress", "2026-10-04: started\n"))
    put(r, g + "PLAN.md", "# plan\n")
    put(r, T + "2026-10-03-0900-build-noplan/STATE.md", state("No plan", "writing requirements"))
    put(r, T + "2026-10-03-1000-research-q/STATE.md", state("Research", "findings drafted"))
    put(r, T + "2026-10-03-1100-build-wait/STATE.md", state("Wait", "awaiting plan approval"))
    put(r, T + "2026-10-03-1200-build-stuck/STATE.md", state("Stuck", "stalled after 3 retries; blocked on API"))
    put(r, T + "2026-10-03-1300-build-fin/STATE.md", state("Fin", "done: merged"))
    put(r, T + "2026-10-03-1400-build-rev/STATE.md", state("Rev", "in review"))
    put(r, T + "2026-10-03-1400-build-rev/PLAN.md", "# p\n")
    put(r, T + "2026-10-05-1500-review-pr7/DRAFT.md", "# Review of PR 7\n\nfindings\nready to post\n")
    p = T + "2026-10-06-0900-build-epic/"
    put(r, p + "STATE.md", state("Epic", "done"))
    put(r, p + "01-build-a/STATE.md", state("A", "done"))
    put(r, p + "02-build-b/STATE.md", state("B", "building"))
    put(r, p + "02-build-b/PLAN.md", "# p\n")
    q = T + "2026-10-07-0900-build-allkids/"
    put(r, q + "STATE.md", state("All kids", "building"))
    put(r, q + "01-build-a/STATE.md", state("A", "done"))
    put(r, T + "_template/STATE.md", state("", ""))
    put(r, T + ".archived/2026-01-01-0900-build-old/STATE.md", state("Old", "done"))
    return r


def by_folder(doc):
    return {t["folder"]: t for t in doc["tasks"]}


def mc_columns(root):
    cache = {}
    for _, src in mc_tasks._iter_task_dirs(root):
        cache[(str(root), src.parent.name)] = (time.monotonic(), None)
    cards = mc_tasks.build_cards(
        [SimpleNamespace(label="p", root=root)],
        heartbeat_dir=root / "no-markers", gh_cache=cache, gh_ttl=1e9,
    )
    return {c["folder"]: c for c in cards}


def test_phase_matches_mission_control(proj):
    got = by_folder(te.build(proj))
    want = mc_columns(proj)
    for folder, task in got.items():
        assert task["phase"] == want[folder]["column"], folder
        assert task["needs_attention"] == want[folder]["needs_attention"], folder
        assert task["kind"] == want[folder]["kind"], folder
        assert task["parent"] == want[folder]["parent"], folder


def test_fixture_phases_cover_every_stage(proj):
    phases = {t["phase"] for t in te.build(proj)["tasks"]}
    assert phases == {
        "planned", "building", "scoping", "awaiting_approval", "blocked",
        "done", "in_review", "parent_tasks",
    }


def test_goal_and_key_info_match_state_schema_parse(proj):
    got = by_folder(te.build(proj))
    for path in (proj / "docs/tasks").glob("**/STATE.md"):
        rel = path.parent.relative_to(proj).as_posix()
        if rel in got:
            fm = state_schema.parse(path.read_text())
            assert (got[rel]["goal"], got[rel]["key_info"]) == (fm["goal"], fm["key_info"])


def test_template_and_default_archive_excluded(proj):
    folders = by_folder(te.build(proj))
    assert not any("_template" in f or ".archived" in f for f in folders)


def test_configured_archive_excludes_that_folder_only(proj):
    put(proj, ".harness/workflow.md", "## Archive\n- Path: docs/tasks/old/\n")
    put(proj, T + "old/2025-01-01-0900-build-x/STATE.md", state("X", "done"))
    folders = by_folder(te.build(proj))
    assert not any(f.startswith(T + "old/") for f in folders)
    assert any(".archived" in f for f in folders)  # default no longer applies


def test_invalid_archive_path_means_no_exclusion(proj):
    put(proj, ".harness/workflow.md", "## Archive\n- Path: ../outside/\n")
    assert any(".archived" in f for f in by_folder(te.build(proj)))


def test_draft_only_folder(proj):
    t = by_folder(te.build(proj))[T + "2026-10-05-1500-review-pr7"]
    assert (t["kind"], t["phase"], t["goal"], t["key_info"], t["last_log"]) == (
        "review", "in_review", "Review of PR 7", "ready to post", None)


def test_subtask_parent_and_last_log(proj):
    got = by_folder(te.build(proj))
    p = T + "2026-10-06-0900-build-epic"
    assert got[p + "/02-build-b"]["parent"] == p
    assert got[p]["parent"] is None
    assert got[p]["phase"] == "parent_tasks"  # own key_info says done, a child is not
    assert got[T + "2026-10-07-0900-build-allkids"]["phase"] == "done"
    assert got[T + "2026-10-01-0900-build-feature"]["last_log"] == "2026-10-03 10:15"
    assert got[T + "2026-10-02-0900-build-building"]["last_log"] == "2026-10-04"
    assert got[T + "2026-10-03-1100-build-wait"]["last_log"] is None


def test_without_docs_tasks_exports_empty_list(tmp_path):
    (tmp_path / ".cairn").mkdir()
    assert te.build(tmp_path)["tasks"] == []


def rec(session, task, start, end, project="/x"):
    return {"session": session, "project": project, "task": task, "start": start, "end": end}


def test_merge_takes_min_start_and_max_end():
    a = rec("s", "t", "2026-10-01T10:00:00Z", "2026-10-01T10:05:00Z")
    b = rec("s", "t", "2026-10-01T09:00:00Z", "2026-10-01T10:30:00Z")
    c = rec("s", "u", "2026-10-01T11:00:00Z", "2026-10-01T11:01:00Z")
    out = te.merge([a, b, c])
    assert len(out) == 2
    t = next(r for r in out if r["task"] == "t")
    assert (t["start"], t["end"]) == ("2026-10-01T09:00:00Z", "2026-10-01T10:30:00Z")


def test_ledger_skips_bad_lines_and_feeds_sessions(proj):
    task = T + "2026-10-02-0900-build-building"
    lines = [
        json.dumps(rec("s2", task, "2026-10-04T09:00:00Z", "2026-10-04T09:10:00Z", str(proj))),
        "not json",
        json.dumps({"session": "x"}),
        json.dumps(rec("s1", task, "2026-10-04T08:00:00Z", "2026-10-04T08:20:00Z", str(proj))),
        json.dumps(rec("s1", task, "2026-10-04T08:10:00Z", "2026-10-04T08:50:00Z", str(proj))),
        json.dumps(rec("s9", "docs/tasks/gone", "2026-10-04T08:10:00Z", "2026-10-04T08:50:00Z", str(proj))),
    ]
    (proj / ".cairn/task-sessions.jsonl").write_text("\n".join(lines) + "\n")
    t = by_folder(te.build(proj))[task]
    assert t["sessions"] == [
        {"session_id": "s1", "started": "2026-10-04T08:00:00Z", "ended": "2026-10-04T08:50:00Z"},
        {"session_id": "s2", "started": "2026-10-04T09:00:00Z", "ended": "2026-10-04T09:10:00Z"},
    ]


def test_ledger_compacts_above_threshold(proj, monkeypatch):
    monkeypatch.setattr(te, "COMPACT_ABOVE", 3)
    task = T + "2026-10-02-0900-build-building"
    ledger = proj / ".cairn/task-sessions.jsonl"
    ledger.write_text("".join(
        json.dumps(rec("s", task, f"2026-10-04T08:0{i}:00Z", f"2026-10-04T08:1{i}:00Z", str(proj))) + "\n"
        for i in range(5)))
    te.export(proj)
    lines = ledger.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["start"] == "2026-10-04T08:00:00Z"
    assert json.loads(lines[0])["end"] == "2026-10-04T08:14:00Z"


def test_pointer_sample_appends_with_session_log_start(proj, tmp_path, monkeypatch):
    home = tmp_path / "home"
    task = T + "2026-10-02-0900-build-building"
    ptr = home / ".claude/cairn/active/sess1.json"
    ptr.parent.mkdir(parents=True)
    ptr.write_text(json.dumps({"project": str(proj), "task": task}))
    (proj / ".cairn/sessions.log").write_text("2026-10-04T07:00:00Z\t3.2.0\tsess1\n2026-10-04T07:30:00Z\t3.2.0\tother\n")
    monkeypatch.setenv("HOME", str(home))
    out = te.export(proj, "sess1", now="2026-10-04T09:00:00Z")
    got = by_folder(json.loads(out.read_text()))[task]["sessions"]
    assert got == [{"session_id": "sess1", "started": "2026-10-04T07:00:00Z", "ended": "2026-10-04T09:00:00Z"}]


def test_pointer_for_other_project_or_bad_session_is_ignored(proj, tmp_path, monkeypatch):
    home = tmp_path / "home"
    ptr = home / ".claude/cairn/active/sess1.json"
    ptr.parent.mkdir(parents=True)
    ptr.write_text(json.dumps({"project": "/elsewhere", "task": T + "x"}))
    monkeypatch.setenv("HOME", str(home))
    te.export(proj, "sess1")
    te.export(proj, "../sess1")
    assert not (proj / ".cairn/task-sessions.jsonl").exists()


def test_atomic_output_shape_and_idempotent(proj):
    out = te.export(proj, now="2026-10-08T00:00:00Z")
    doc = json.loads(out.read_text())
    assert list(doc)[:4] == ["schema", "generated", "project", "tasks"]
    assert doc["schema"] == 1 and doc["project"] == str(proj.resolve())
    assert doc["generated"] == "2026-10-08T00:00:00Z"
    te.export(proj, now="2026-10-09T00:00:00Z")  # nothing changed: file kept
    assert json.loads(out.read_text())["generated"] == "2026-10-08T00:00:00Z"
    assert [p.name for p in out.parent.iterdir()] == ["tasks.json"]
    put(proj, T + "2026-10-10-0900-build-new/STATE.md", state("New", "x"))
    te.export(proj, now="2026-10-10T00:00:00Z")
    assert json.loads(out.read_text())["generated"] == "2026-10-10T00:00:00Z"


def test_no_cairn_dir_writes_nothing(tmp_path):
    assert te.export(tmp_path) is None
    assert not (tmp_path / ".cairn").exists()


def test_cli_exits_zero_and_writes(proj):
    r = subprocess.run([sys.executable, str(SCRIPT), "--root", str(proj)], capture_output=True, text=True)
    assert r.returncode == 0
    assert (proj / ".cairn/export/tasks.json").is_file()
    r = subprocess.run([sys.executable, str(SCRIPT), "--root", "/nonexistent-x"], capture_output=True, text=True)
    assert r.returncode == 0
