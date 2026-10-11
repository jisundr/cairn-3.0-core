"""Runs the rewrite command from plugin/skills/shared/reference/marker-task.md against fixture markers."""
import json
import os
import re
import subprocess
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
