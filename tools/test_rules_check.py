import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "plugin/skills/task-assets/assets"
CHECKER = ASSETS / "rules-check.py"
SPEC = ASSETS / "rule-format.md"

_spec = importlib.util.spec_from_file_location("rules_check", CHECKER)
rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rc)

HEADER = "> header line\n\n"


def harness(tmp_path, **files):
    h = tmp_path / ".harness"
    h.mkdir(exist_ok=True)
    for name, body in files.items():
        (h / (name + ".md")).write_text(HEADER + body, encoding="utf-8")
    return tmp_path


def states(root):
    return [(r["text"], r["state"]) for r in rc.scan(root)]


def test_legacy_20_file_is_valid_not_malformed(tmp_path):
    root = harness(tmp_path, standards="## Naming\n- Use dashes\n- Lowercase names\n")
    res = rc.scan(root)
    assert [r["state"] for r in res] == ["legacy", "legacy"]
    assert all(r["trigger"] is None for r in res)


def test_non_rules_are_skipped(tmp_path):
    body = (
        "## Gates\n- python tools/budget.py clean\n\n"
        "## Release\n- Tag: v{version}\n\n"
        "## Naming\n```\n- inside fence\n```\nplain prose\n- real rule\n"
    )
    root = harness(tmp_path, workflow=body)
    assert states(root) == [("real rule", "legacy")]


def test_gates_and_release_variants_are_skipped(tmp_path):
    body = (
        "## Gates (additive)\n- python tools/budget.py clean\n\n"
        "## Release process\n- Tag: v{version}\n\n"
        "## Gatesmith\n- real rule\n"
    )
    root = harness(tmp_path, workflow=body)
    assert states(root) == [("real rule", "legacy")]


def test_typed_preconditions_are_not_rules(tmp_path):
    body = (
        "## Checks\n"
        "- [blocking] python >=3.11\n"
        "- [Warning] command \"jq -V\"\n"
        "tool-version node >=20   [warning]\n"
        "- real rule\n"
    )
    root = harness(tmp_path, environment=body)
    assert states(root) == [("real rule", "legacy")]
    assert rc.parse_rule_line("- [blocking] x") is None
    assert rc.parse_rule_line("- [other] x") is not None


def test_path_evidence_goes_stale_when_file_removed(tmp_path):
    root = harness(tmp_path, standards="## A\n- Keep it | evidence: path:src/a.py\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/a.py").write_text("x")
    assert states(root) == [("Keep it", "verified")]
    (tmp_path / "src/a.py").unlink()
    assert states(root) == [("Keep it", "stale")]


def test_path_glob_evidence(tmp_path):
    root = harness(tmp_path, standards="## A\n- r | evidence: path:src/**/*.go\n")
    (tmp_path / "src/x").mkdir(parents=True)
    assert states(root)[0][1] == "stale"
    (tmp_path / "src/x/m.go").write_text("")
    assert states(root)[0][1] == "verified"


def test_correction_is_unverifiable_not_stale(tmp_path):
    root = harness(tmp_path, standards="## A\n- r | evidence: correction:2026-10-11 user said so\n")
    assert states(root) == [("r", "unverifiable")]


def test_cmd_package_json(tmp_path):
    root = harness(tmp_path, workflow="## A\n- one | evidence: cmd:package.json#build\n- two | evidence: cmd:package.json#lint\n")
    assert [s for _, s in states(root)] == ["stale", "stale"]
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"build": "x"}}))
    assert [s for _, s in states(root)] == ["verified", "stale"]


def test_cmd_makefile_target(tmp_path):
    root = harness(tmp_path, workflow="## A\n- one | evidence: cmd:Makefile#test\n- two | evidence: cmd:Makefile#deploy\n")
    (tmp_path / "Makefile").write_text("VAR := 1\ntest: deps\n\tpytest\n")
    assert [s for _, s in states(root)] == ["verified", "stale"]


def test_unsupported_manifest_and_untyped_are_unverifiable(tmp_path):
    root = harness(tmp_path, workflow="## A\n- a | evidence: cmd:Cargo.toml#build\n- b | evidence: seen in review\n")
    assert [s for _, s in states(root)] == ["unverifiable", "unverifiable"]


def test_malformed_cases(tmp_path):
    body = (
        "## A\n"
        "- empty | evidence: \n"
        "- baddate | evidence: correction:2026-13-40 x\n"
        "- notext | evidence: correction:2026-10-11\n"
        "- nohash | evidence: cmd:Makefile\n"
        "- badtrig | applies when: sometimes\n"
        "- badkind | applies when: kind:deploy\n"
        "- order | applies when: always | evidence: path:a\n"
    )
    root = harness(tmp_path, standards=body)
    assert [s for _, s in states(root)] == ["malformed"] * 7


def test_pipe_in_text_is_fine(tmp_path):
    rule = rc.parse_rule_line("- a | b is ok | evidence: path:x | applies when: always")
    assert rule == {"text": "a | b is ok", "evidence": "path:x", "trigger": "always"}


def test_select_docs_task_skips_src_rules(tmp_path):
    body = (
        "## A\n"
        "- docs rule | applies when: paths:docs/**\n"
        "- src rule | applies when: paths:src/**\n"
        "- bare dir rule | applies when: paths:docs\n"
        "- always rule | applies when: always\n"
        "- untriggered\n"
    )
    root = harness(tmp_path, standards=body)
    loaded = {r["text"] for r in rc.scan(root) if rc.matches(r, ["docs/"], "build")}
    assert loaded == {"docs rule", "bare dir rule", "always rule", "untriggered"}
    loaded = {r["text"] for r in rc.scan(root) if rc.matches(r, ["docs/guide/x.md"], "build")}
    assert "src rule" not in loaded and "docs rule" in loaded


def test_paths_nesting_and_file_globs():
    rule = {"trigger": "paths:src/**/*.go"}
    assert rc.matches(rule, ["src/a/b.go"])
    assert not rc.matches(rule, ["src/a/b.py"])
    assert rc.matches(rule, ["src/"])
    assert not rc.matches(rule, ["docs/"])


def test_kind_trigger_and_malformed_fails_open():
    rule = {"trigger": "kind:review, research"}
    assert rc.matches(rule, [], "review")
    assert not rc.matches(rule, [], "build")
    assert rc.matches({"trigger": "kind:deploy"}, [], "build")
    assert rc.matches({"trigger": None}, [], "build")


def spec_examples():
    text = SPEC.read_text(encoding="utf-8")
    return [b.strip() for b in re.findall(r"```\n(.*?)\n```", text, re.S)]


def test_spec_examples_round_trip(tmp_path):
    examples = spec_examples()
    assert len(examples) == 4
    root = harness(tmp_path, standards="## A\n" + "\n".join(examples) + "\n")
    (tmp_path / "plugin/hooks").mkdir(parents=True)
    (tmp_path / "plugin/hooks/a.sh").write_text("")
    (tmp_path / "Makefile").write_text("test:\n")
    res = rc.scan(root)
    assert [r["state"] for r in res] == ["verified", "verified", "unverifiable", "legacy"]
    assert res[3]["trigger"] == "kind:research, review"


def test_repo_harness_has_no_malformed():
    res = rc.scan(ROOT)
    assert res and not [r for r in res if r["state"] == "malformed"]


def test_cli_report_exit_0_and_select(tmp_path):
    root = harness(tmp_path, standards="## A\n- docs | applies when: paths:docs/**\n- src | applies when: paths:src/**\n")
    base = [sys.executable, str(CHECKER), "--root", str(root)]
    out = subprocess.run(base, capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.startswith("rules: 2")
    out = subprocess.run(base + ["--select", "docs/", "--kind", "build"], capture_output=True, text=True)
    assert out.returncode == 0 and "docs" in out.stdout and "src" not in out.stdout.split("\n", 1)[1]


def test_legacy_lines_are_capped(tmp_path):
    root = harness(tmp_path, standards="## A\n" + "".join("- rule %d\n" % i for i in range(14)))
    lines, counts = rc.report(rc.scan(root))
    assert counts["legacy"] == 14
    assert lines[-1] == "+4 more legacy"
    assert len(lines) == 1 + 10 + 1
