"""Runs the rewrite command from plugin/skills/shared/reference/marker-task.md against fixture markers."""
import json
import os
import re
import subprocess
import time
from pathlib import Path

REF = Path(__file__).resolve().parent.parent / "plugin/skills/shared/reference/marker-task.md"
NAME = "s1--a1.active"


def command():
    m = re.search(r"```bash\n(.*?)\n```", REF.read_text(), re.S)
    assert m, "no fenced bash command in marker-task.md"
    return m.group(1)


def run(home, folder, marker=NAME):
    env = {**os.environ, "HOME": str(home), "F": folder, "M": marker}
    return subprocess.run(["bash", "-c", command()], env=env, capture_output=True, text=True)


def active(tmp_path):
    d = tmp_path / ".claude/cairn/active"
    d.mkdir(parents=True)
    return d


def test_rewrites_task_and_keeps_project(tmp_path):
    d = active(tmp_path)
    (d / NAME).write_text('{"project":"/p","task":"docs/tasks/parent"}')
    r = run(tmp_path, "docs/tasks/parent/02-build-x")
    assert r.returncode == 0
    assert json.loads((d / NAME).read_text()) == {"project": "/p", "task": "docs/tasks/parent/02-build-x"}


def test_leaves_no_stray_active_file(tmp_path):
    d = active(tmp_path)
    (d / NAME).write_text('{"project":"/p","task":"t"}')
    run(tmp_path, "docs/tasks/a")
    assert [p.name for p in d.glob("*.active")] == [NAME]


def test_missing_marker_exits_zero_and_creates_nothing(tmp_path):
    d = active(tmp_path)
    r = run(tmp_path, "docs/tasks/a")
    assert r.returncode == 0
    assert list(d.iterdir()) == []


def test_empty_folder_leaves_marker_untouched(tmp_path):
    d = active(tmp_path)
    body = '{"project":"/p","task":"t"}'
    (d / NAME).write_text(body)
    r = run(tmp_path, "")
    assert r.returncode == 0
    assert (d / NAME).read_text() == body


HOOK = Path(__file__).resolve().parent.parent / "plugin/hooks/subagent-marker.sh"


def hook(home, event, session="s1", agent="a1"):
    env = {**os.environ, "HOME": str(home)}
    stdin = json.dumps({"session_id": session, "agent_id": agent})
    return subprocess.run([str(HOOK), event], input=stdin, env=env, capture_output=True, text=True)


def test_retask_keeps_schema_and_started(tmp_path):
    d = active(tmp_path)
    (d / NAME).write_text('{"project":"/p","task":"a","schema":1,"started":"2026-01-01T00:00:00Z"}')
    run(tmp_path, "docs/tasks/b")
    assert json.loads((d / NAME).read_text()) == {
        "project": "/p", "task": "docs/tasks/b", "schema": 1, "started": "2026-01-01T00:00:00Z"}


def test_start_stamps_schema_and_started_then_stop_appends_retasked_ledger_line(tmp_path):
    d = active(tmp_path)
    proj = tmp_path / "proj"
    (proj / ".cairn").mkdir(parents=True)
    (d / "s1.json").write_text(json.dumps({"project": str(proj), "task": "docs/tasks/parent"}))
    assert hook(tmp_path, "start").returncode == 0
    marker = json.loads((d / NAME).read_text())
    assert marker["schema"] == 1 and marker["task"] == "docs/tasks/parent"
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", marker["started"])
    run(tmp_path, "docs/tasks/parent/01-build-x")
    assert hook(tmp_path, "stop").returncode == 0
    assert not (d / NAME).exists()
    lines = (proj / ".cairn/task-sessions.jsonl").read_text().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert (rec["session"], rec["project"], rec["task"]) == ("s1", str(proj), "docs/tasks/parent/01-build-x")
    assert rec["start"] == marker["started"] and rec["end"] >= rec["start"]


def test_stop_without_cairn_dir_or_started_stays_quiet(tmp_path):
    d = active(tmp_path)
    proj = tmp_path / "bare"
    proj.mkdir()
    (d / NAME).write_text(json.dumps({"project": str(proj), "task": "t"}))
    assert hook(tmp_path, "stop").returncode == 0
    assert not (d / NAME).exists()
    assert list(proj.iterdir()) == []
    # an older marker (no started) in a project that has .cairn: start falls back to end
    (proj / ".cairn").mkdir()
    (d / NAME).write_text(json.dumps({"project": str(proj), "task": "t"}))
    hook(tmp_path, "stop")
    rec = json.loads((proj / ".cairn/task-sessions.jsonl").read_text())
    assert rec["start"] == rec["end"]


def test_sweep_deletes_only_markers_older_than_240_minutes(tmp_path):
    d = active(tmp_path)
    now = time.time()
    ages = {"old--a.active": 241, "edge--a.active": 239, "new--a.active": 0}
    for name, minutes in ages.items():
        p = d / name
        p.write_text("{}")
        os.utime(p, (now - minutes * 60, now - minutes * 60))
    assert hook(tmp_path, "sweep").returncode == 0
    assert sorted(p.name for p in d.glob("*.active")) == ["edge--a.active", "new--a.active"]


def test_start_without_session_pointer_writes_nothing_and_prints_nothing(tmp_path):
    d = active(tmp_path)
    r = hook(tmp_path, "start", session="nosuch")
    assert r.returncode == 0
    assert r.stdout == "" and r.stderr == ""
    assert list(d.iterdir()) == []
