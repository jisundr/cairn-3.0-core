"""CONTEXT.md manifest: template size, Inputs paths, derivation parity,
sub-task numbering, and the context-layer cap table."""
import importlib.util
import re
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "plugin/skills/task-assets/assets/tasks/_template/CONTEXT.md"
LAYERS = ROOT / "plugin/skills/start/reference/context-layers.md"
MC_TASKS = ROOT / "plugin/mission-control/tasks.py"

spec = importlib.util.spec_from_file_location("mc_tasks_under_test", MC_TASKS)
mc_tasks = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mc_tasks
spec.loader.exec_module(mc_tasks)

MANIFEST_LINE_CAP = 80
DEFAULT_BUDGET = 40_000
ESCALATED_BUDGET = 150_000

POPULATED = """\
> Per-stage inputs and outputs.

## Plan
| Inputs: source | file or section | why |
|---|---|---|
| task | REQUIREMENTS.md | goal and constraints |
| repo | src/app.py | the code to change |

| Outputs: file | produced by |
|---|---|
| PLAN.md | planner |
"""


def inputs_paths(text):
    """File paths from every Inputs table: the second column of its rows."""
    paths, in_inputs = [], False
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells[0].startswith("Inputs:"):
                in_inputs = True
            elif cells[0].startswith("Outputs:"):
                in_inputs = False
            elif in_inputs and not set(cells[0]) <= {"-"} and len(cells) >= 2 and cells[1]:
                paths.append(cells[1].split("#")[0].strip())
        else:
            in_inputs = False
    return paths


def next_subtask_number(folder):
    nums = [int(m.group(1)) for p in folder.iterdir() if p.is_dir() and (m := re.match(r"(\d{2})-", p.name))]
    return max(nums, default=0) + 1


def state(key_info):
    return f"---\nschema: 1\ngoal: g\nkey_info: {key_info}\n---\n"


def make_folder(root, name, key_info, plan, context, subtasks=()):
    folder = root / "docs/tasks" / name
    folder.mkdir(parents=True)
    (folder / "STATE.md").write_text(state(key_info))
    (folder / "REQUIREMENTS.md").write_text("r\n")
    if plan:
        (folder / "PLAN.md").write_text("p\n")
    if context:
        (folder / "CONTEXT.md").write_text(POPULATED)
    for sub, sub_key in subtasks:
        d = folder / sub
        d.mkdir()
        (d / "STATE.md").write_text(state(sub_key))
        (d / "PLAN.md").write_text("p\n")
    return folder


def columns(root):
    project = SimpleNamespace(label="p", root=root)
    cards = mc_tasks.build_cards(
        [project], heartbeat_dir=root / "no-heartbeats", now=0.0, gh_cache={("x", "x"): None}
    )
    return {c["folder"]: c["column"] for c in cards}


def test_template_within_cap_and_inputs_paths_exist(tmp_path):
    assert len(TEMPLATE.read_text().splitlines()) <= 40
    assert len(POPULATED.splitlines()) <= MANIFEST_LINE_CAP
    (tmp_path / "src").mkdir()
    (tmp_path / "REQUIREMENTS.md").write_text("r\n")
    (tmp_path / "src/app.py").write_text("x\n")
    paths = inputs_paths(POPULATED)
    assert paths == ["REQUIREMENTS.md", "src/app.py"]
    assert all((tmp_path / p).exists() for p in paths)


def test_stage_derivation_identical_with_and_without_manifest(tmp_path):
    cases = [
        ("a-build-nonplan", "approved: write plan", False, ()),
        ("b-build-planned", "approved", True, ()),
        ("c-build-building", "building step 2", True, ()),
        ("d-build-awaiting", "awaiting plan approval", True, ()),
        ("e-build-parent", "approved", True, (("01-build-x", "done"), ("02-build-y", "building"))),
    ]
    with_ctx, without_ctx = tmp_path / "with", tmp_path / "without"
    for root, ctx in ((with_ctx, True), (without_ctx, False)):
        for name, key, plan, subs in cases:
            make_folder(root, name, key, plan, ctx, subs)
    got_with, got_without = columns(with_ctx), columns(without_ctx)
    assert got_with == got_without
    assert len(got_with) == len(cases) + 2
    assert got_with["docs/tasks/e-build-parent"] == "parent_tasks"
    assert got_with["docs/tasks/b-build-planned"] == "planned"


def test_subtask_numbering_ignores_context_file(tmp_path):
    a = make_folder(tmp_path / "a", "t", "approved", True, True, (("01-build-x", "done"), ("02-build-y", "done")))
    b = make_folder(tmp_path / "b", "t", "approved", True, False, (("01-build-x", "done"), ("02-build-y", "done")))
    assert next_subtask_number(a) == next_subtask_number(b) == 3


def test_layer_caps_fit_budgets():
    default = escalated = 0
    for line in LAYERS.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) == 4 and cells[0].isdigit():
            default += int(cells[2])
            escalated += int(cells[3])
    assert default > 0 and escalated > 0
    assert default <= DEFAULT_BUDGET
    assert escalated <= ESCALATED_BUDGET
