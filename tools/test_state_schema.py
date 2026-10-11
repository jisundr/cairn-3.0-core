import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import budget  # noqa: E402
import state_schema as ss  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = [
    ROOT / "plugin/skills/task-assets/assets/tasks/_template/STATE.md",
    ROOT / "docs/tasks/_template/STATE.md",
]

MINIMAL_20 = "---\ngoal: Fix the thing\nkey_info: building\n---\n2026-01-01 10:00: created\n"

FLOW_LISTS = (
    "---\nschema: 1\ngoal: g\npaths: [a/, \"b, c\"]\ndone_when: d\nout_of_scope: []\n"
    "source: ../R.md\npath: escalated\nkey_info: k\nflags: [x, y]\n---\nlog\n"
)

BLOCK_LISTS = (
    "---\ngoal: g\npaths:\n  - a/\n  - 'b'\nkey_info: k\nflags:\n  - one\n  - two\n---\n"
)

SUBTASK = "---\ngoal: g\ndepends_on: [01]\nkey_info: k\n---\n"
SUBTASK_PARENT = "---\ngoal: g\ndepends_on: [parent]\nkey_info: k\n---\n"

# The shape of an epic's own STATE.md in this task tree.
OWN_SHAPE = (
    "---\n"
    "goal: Publish STATE.md frontmatter as a versioned schema (schema: 1) in core\n"
    'paths: [docs/schemas/, tools/*state_schema.py, "**/tasks/_template/STATE.md", docs/README.md]\n'
    "done_when: STATE.md schema:1 is published, and 2.0 STATE.md files validate or have a migration\n"
    "out_of_scope: [tasks.json export and writer, usage.json schema, board UI]\n"
    "source: ../REQUIREMENTS.md\n"
    "path: escalated\n"
    "depends_on: [01]\n"
    "key_info: PLAN.md approved. Next: builder on branch 02-build-contracts in core/.\n"
    "flags: [schema absent reads as 1; only goal+key_info required]\n"
    "---\n\n2026-10-11 01:12: sub-task created\n"
)

VALID = [MINIMAL_20, FLOW_LISTS, BLOCK_LISTS, SUBTASK, SUBTASK_PARENT, OWN_SHAPE]


def errors(text):
    return [f for f in ss.validate(text) if f.severity == "error"]


def warnings(text):
    return [f for f in ss.validate(text) if f.severity == "warning"]


@pytest.mark.parametrize("text", VALID)
def test_valid_fixtures_have_no_errors(text):
    assert errors(text) == []


def test_2_0_file_without_schema_key_is_clean():
    assert ss.validate(MINIMAL_20) == []


def test_parse_reads_flow_and_block_lists():
    assert ss.parse(FLOW_LISTS)["paths"] == ["a/", "b, c"]
    assert ss.parse(BLOCK_LISTS)["paths"] == ["a/", "b"]
    assert ss.parse(SUBTASK)["depends_on"] == ["01"]


def test_unclosed_frontmatter_is_error():
    assert errors("---\ngoal: g\nkey_info: k\n")


def test_no_frontmatter_is_error():
    assert errors("goal: g\n")


@pytest.mark.parametrize("missing", ["goal", "key_info"])
def test_missing_required_field_is_error(missing):
    lines = [l for l in MINIMAL_20.splitlines() if not l.startswith(missing + ":")]
    found = errors("\n".join(lines) + "\n")
    assert [f.field for f in found] == [missing]


@pytest.mark.parametrize("value", ["x", "0", "-1", "1.5", "[1]"])
def test_bad_schema_value_is_error(value):
    text = MINIMAL_20.replace("---\ngoal", f"---\nschema: {value}\ngoal", 1)
    assert [f.field for f in errors(text)] == ["schema"]


def test_newer_schema_is_warning_not_error():
    text = MINIMAL_20.replace("---\ngoal", "---\nschema: 2\ngoal", 1)
    assert errors(text) == []
    assert [f.field for f in warnings(text)] == ["schema"]


def test_list_field_given_scalar_is_error():
    text = MINIMAL_20.replace("key_info", "paths: docs/\nkey_info", 1)
    assert [f.field for f in errors(text)] == ["paths"]


def test_unknown_key_is_warning():
    text = MINIMAL_20.replace("key_info", "colour: blue\nkey_info", 1)
    assert errors(text) == []
    assert [f.field for f in warnings(text)] == ["colour"]


def test_long_field_is_warning():
    text = MINIMAL_20.replace("Fix the thing", "x" * 250)
    assert errors(text) == []
    assert any(f.field == "goal" for f in warnings(text))


def test_oversized_block_is_error_and_soft_zone_is_warning():
    big = "---\ngoal: g\nkey_info: k\nflags: [" + ", ".join(["y" * 90] * 12) + "]\n---\n"
    assert ss._block_bytes(big) > ss.BLOCK_HARD
    assert any(f.field is None for f in errors(big))
    soft = "---\ngoal: g\nkey_info: k\nflags: [" + ", ".join(["y" * 90] * 9) + "]\n---\n"
    assert ss.BLOCK_SOFT < ss._block_bytes(soft) <= ss.BLOCK_HARD
    assert errors(soft) == []
    assert any(f.field is None for f in warnings(soft))


# Conformance with the other readers and writers of STATE.md.


def load_tasks():
    path = ROOT / "mission-control" / "tasks.py"
    if not path.is_file():
        pytest.skip("mission-control/tasks.py absent")
    spec = importlib.util.spec_from_file_location("mc_tasks", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("text", VALID + ["---\ngoal:\npaths: []\nkey_info:\n---\n", "---\ngoal: g\n"])
def test_parse_matches_mission_control(text):
    tasks = load_tasks()
    assert ss.parse(text) == tasks.parse_frontmatter(text)


def test_caps_match_budget_gate():
    src = Path(budget.__file__).read_text()
    assert f'"task-state", rel, size, "B", {ss.BLOCK_SOFT}, {ss.BLOCK_HARD}' in src


def test_block_bytes_match_budget_measure():
    for text in VALID:
        assert ss._block_bytes(text) == budget.frontmatter_bytes(text)


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.parent.parent.parent.name)
def test_template_validates_and_declares_schema_1(path):
    text = path.read_text()
    assert errors(text) == []
    assert ss.parse(text)["schema"] == "1"
    assert list(ss.parse(text))[0] == "schema"


def test_templates_share_one_frontmatter():
    def block(p):
        lines = p.read_text().splitlines()
        return lines[: lines.index("---", 1) + 1]

    assert block(TEMPLATES[0]) == block(TEMPLATES[1])
