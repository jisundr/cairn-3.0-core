import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import upgrade_check as uc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def test_fixture_upgrades_cleanly():
    notes, misses = uc.check(uc.FIXTURE)
    assert misses == []
    joined = "\n".join(notes)
    assert "legacy" in joined and "0 malformed" in joined
    assert "byte-identical" in joined


def test_fixture_is_a_2_0_harness():
    names = sorted(p.name for p in (uc.FIXTURE / ".harness").glob("*.md"))
    assert names == ["architecture.md", "environment.md", "standards.md", "workflow.md"]
    text = "".join(p.read_text() for p in (uc.FIXTURE / ".harness").glob("*.md"))
    assert "evidence:" not in text, "a 2.0 harness carries no evidence lines"


def test_upgrade_detects_a_rewritten_harness_file(monkeypatch):
    real_run = uc.run

    def rewriting_run(cmd, env, **kw):
        if "--root" in cmd:
            target = Path(cmd[cmd.index("--root") + 1]) / ".harness" / "workflow.md"
            target.write_text(target.read_text() + "\n- added by a script\n")
        return real_run(cmd, env, **kw)

    monkeypatch.setattr(uc, "run", rewriting_run)
    _, misses = uc.check(uc.FIXTURE)
    assert ".harness/workflow.md: changed" in misses


def test_upgrade_detects_a_new_file_outside_cairn(monkeypatch):
    real_run = uc.run

    def littering_run(cmd, env, **kw):
        if "--root" in cmd:
            (Path(cmd[cmd.index("--root") + 1]) / "stray.txt").write_text("x")
        return real_run(cmd, env, **kw)

    monkeypatch.setattr(uc, "run", littering_run)
    _, misses = uc.check(uc.FIXTURE)
    assert "stray.txt: new file outside .cairn/" in misses


def test_repo_without_marker_is_a_miss(tmp_path):
    shutil.copytree(uc.FIXTURE / ".harness", tmp_path / ".harness")
    (tmp_path / "CLAUDE.md").write_text("# plain\n")
    _, misses = uc.check(tmp_path)
    assert len(misses) == 1 and "marker" in misses[0]


def test_mission_control_hooks_and_command_still_ship():
    hooks = json.loads((ROOT / "plugin/hooks/hooks.json").read_text())
    commands = [h["command"] for g in hooks["hooks"].values() for e in g for h in e["hooks"]]
    assert any("stop-mc.sh" in c for c in commands)
    assert (ROOT / "plugin/commands/cairn-mc.md").is_file()


def test_plugin_version_matches_the_changelog_heading():
    manifest = json.loads((ROOT / "plugin/.claude-plugin/plugin.json").read_text())
    headings = [ln[3:].split(" ")[0] for ln in (ROOT / "CHANGELOG.md").read_text().splitlines()
                if ln.startswith("## ")]
    assert headings and manifest["version"] == headings[0]
    parts = manifest["version"].split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts)


def _manifest_version():
    return json.loads((ROOT / "plugin/.claude-plugin/plugin.json").read_text())["version"]


def _first_heading():
    for ln in (ROOT / "CHANGELOG.md").read_text().splitlines():
        if ln.startswith("## "):
            return ln[3:].split(" ")[0]


def test_notice_uses_the_real_plugin_version():
    assert _manifest_version() == _first_heading()
    assert uc.TARGET == _manifest_version()
    notes, misses = uc.check(uc.FIXTURE)
    if any("session-start.sh" in n for n in notes):
        assert f"cairn updated {uc.PREVIOUS} -> {_manifest_version()}" in "\n".join(notes)
    assert misses == []


def test_harness_with_no_rules_passes_as_zero_rules():
    counts = {"verified": 0, "stale": 0, "unverifiable": 0, "legacy": 0, "malformed": 0}
    note, miss = uc.judge_counts(counts)
    assert miss == "" and "0 rules" in note


def test_harness_with_rules_and_no_legacy_is_a_miss():
    counts = {"verified": 3, "stale": 0, "unverifiable": 0, "legacy": 0, "malformed": 0}
    note, miss = uc.judge_counts(counts)
    assert note == "" and "none legacy" in miss


def test_harness_with_legacy_rules_passes():
    counts = {"verified": 0, "stale": 0, "unverifiable": 0, "legacy": 2, "malformed": 0}
    note, miss = uc.judge_counts(counts)
    assert miss == "" and "2 legacy" in note
