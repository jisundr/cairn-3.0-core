import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import budget  # noqa: E402


def w(root, rel, content):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def agent_md(name="builder", description="x", tools="Read, Write", body="body text"):
    return f"---\nname: {name}\ndescription: {description}\ntools: {tools}\n---\n{body}\n"


def errs(findings):
    return [f for f in findings if f.severity == "error"]


def test_agent_description_cap(tmp_path):
    w(tmp_path, "agents/builder.md", agent_md(description="short"))
    findings, *_ = budget.gather_findings(tmp_path)
    assert not any(f.rule == "agent-description" for f in findings)

    w(tmp_path, "agents/builder.md", agent_md(description="x" * 400))
    findings, *_ = budget.gather_findings(tmp_path)
    assert any(f.rule == "agent-description" and f.severity == "error" for f in findings)


def test_agent_body_cap(tmp_path):
    w(tmp_path, "agents/builder.md", agent_md(body="y" * 5000))
    findings, *_ = budget.gather_findings(tmp_path)
    assert any(f.rule == "agent-body" and f.severity == "error" for f in findings)


def test_skill_md_cap(tmp_path):
    w(tmp_path, "skills/foo/SKILL.md", "---\nname: foo\ndescription: d\n---\n" + "z" * 5000)
    findings, *_ = budget.gather_findings(tmp_path)
    assert any(f.rule == "skill-md" and f.severity == "error" for f in findings)


def test_skill_reference_cap(tmp_path):
    w(tmp_path, "skills/foo/SKILL.md", "---\nname: foo\ndescription: d\n---\n| File | Load when |\n|---|---|\n| reference/deep.md | always |\n")
    w(tmp_path, "skills/foo/reference/deep.md", "z" * 9000)
    findings, *_ = budget.gather_findings(tmp_path)
    assert any(f.rule == "skill-reference" and f.severity == "error" for f in findings)


def test_command_file_cap(tmp_path):
    w(tmp_path, "commands/setup.md", "---\ndescription: d\n---\n" + "a" * 3000)
    findings, *_ = budget.gather_findings(tmp_path)
    assert any(f.rule == "command-file" and f.severity == "error" for f in findings)


def test_hook_script_cap(tmp_path):
    w(tmp_path, "hooks/session-start.sh", "#!/bin/sh\n" + "echo hi\n" * 500)
    findings, *_ = budget.gather_findings(tmp_path)
    assert any(f.rule == "hook-script" and f.severity == "error" for f in findings)


def test_harness_file_lines_cap(tmp_path):
    w(tmp_path, ".harness/architecture.md", "\n".join(f"line {i}" for i in range(70)))
    findings, *_ = budget.gather_findings(tmp_path)
    assert any(f.rule == "harness-file" and f.severity == "error" for f in findings)


def test_harness_local_prefs_lines_cap(tmp_path):
    w(tmp_path, ".harness/local/preferences.md", "\n".join(f"line {i}" for i in range(40)))
    findings, *_ = budget.gather_findings(tmp_path)
    assert any(f.rule == "harness-local-prefs" and f.severity == "error" for f in findings)


def test_task_plan_cap(tmp_path):
    w(tmp_path, "docs/tasks/foo/plan.md", "p" * 13000)
    findings, *_ = budget.gather_findings(tmp_path)
    assert any(f.rule == "task-plan" and f.severity == "error" for f in findings)


def test_task_plan_cap_uppercase(tmp_path):
    w(tmp_path, "docs/tasks/foo/PLAN.md", "p" * 13000)
    findings, *_ = budget.gather_findings(tmp_path)
    assert any(f.rule == "task-plan" and f.severity == "error" for f in findings)


def test_task_state_cap(tmp_path):
    w(tmp_path, "docs/tasks/foo/STATE.md", "s" * 1500)
    findings, *_ = budget.gather_findings(tmp_path)
    assert any(f.rule == "task-state" and f.severity == "error" for f in findings)


def test_task_files_are_capped_but_not_in_ledger(tmp_path):
    w(tmp_path, "docs/tasks/foo/STATE.md", "---\nkey_info: " + "s" * 1500 + "\n---\n")
    w(tmp_path, "docs/tasks/foo/plan.md", "p" * 100)
    w(tmp_path, "docs/tasks/foo/01-sub/STATE.md", "---\ngoal: g\n---\n")
    findings, rows, _ = budget.gather_findings(tmp_path)
    assert any(f.rule == "task-state" and f.severity == "error" for f in findings)
    assert not any(str(r[0]).startswith("docs/tasks/") for r in rows)


def test_task_state_cap_ignores_log_body(tmp_path):
    w(tmp_path, "docs/tasks/foo/STATE.md", "---\ngoal: g\n---\n" + "log line\n" * 600)
    findings, *_ = budget.gather_findings(tmp_path)
    assert not any(f.rule == "task-state" for f in findings)


def test_task_state_cap_counts_frontmatter(tmp_path):
    w(tmp_path, "docs/tasks/foo/STATE.md", "---\nkey_info: " + "s" * 1500 + "\n---\nbody\n")
    findings, *_ = budget.gather_findings(tmp_path)
    assert any(f.rule == "task-state" and f.severity == "error" for f in findings)


def test_task_state_cap_unclosed_frontmatter_measures_whole_file(tmp_path):
    w(tmp_path, "docs/tasks/foo/STATE.md", "---\nkey_info: " + "s" * 1500 + "\n")
    findings, *_ = budget.gather_findings(tmp_path)
    assert any(f.rule == "task-state" and f.severity == "error" for f in findings)


def test_claude_md_marker_cap(tmp_path):
    w(tmp_path, "skills/task-assets/assets/claude-md-marker.md", "m" * 500)
    findings, *_ = budget.gather_findings(tmp_path)
    assert any(f.rule == "claude-md-marker" and f.severity == "error" for f in findings)


def test_plugin_claude_md_cap(tmp_path):
    w(tmp_path, "CLAUDE.md", "c" * 5000)
    findings, *_ = budget.gather_findings(tmp_path)
    assert any(f.rule == "plugin-claude-md" and f.severity == "error" for f in findings)


def test_runtime_md_catchall_cap(tmp_path):
    w(tmp_path, "skills/misc.md", "q" * 9000)
    findings, *_ = budget.gather_findings(tmp_path)
    assert any(f.rule == "runtime-md-catchall" and f.severity == "error" for f in findings)


def test_always_loaded_total_cap(tmp_path):
    for i in range(15):
        w(tmp_path, f"agents/a{i}.md", agent_md(name=f"a{i}", description="d" * 250))
    findings, *_ = budget.gather_findings(tmp_path)
    assert any(f.rule == "always-loaded-frontmatter-total" and f.severity == "error" for f in findings)


def test_no_at_imports(tmp_path):
    w(tmp_path, "skills/foo/SKILL.md", "---\nname: foo\ndescription: d\n---\n@some/path.md\n")
    findings = budget.check_at_imports(tmp_path)
    assert any(f.rule == "no-at-imports" for f in findings)

    w(tmp_path, "skills/foo/SKILL.md", "---\nname: foo\ndescription: d\n---\nno imports here\n")
    findings = budget.check_at_imports(tmp_path)
    assert not findings


def test_reference_table_orphan(tmp_path):
    w(tmp_path, "skills/foo/SKILL.md", "---\nname: foo\ndescription: d\n---\nno table\n")
    w(tmp_path, "skills/foo/reference/orphan.md", "content")
    findings = budget.check_reference_tables(tmp_path)
    assert any(f.rule == "reference-table-orphan" for f in findings)

    w(tmp_path, "skills/foo/SKILL.md", "---\nname: foo\ndescription: d\n---\nsee reference/orphan.md\n")
    findings = budget.check_reference_tables(tmp_path)
    assert not findings


def test_no_placeholders(tmp_path):
    w(tmp_path, "agents/builder.md", agent_md(body="step 4: <placeholder>"))
    findings = budget.check_placeholders(tmp_path)
    assert any(f.rule == "no-placeholders" for f in findings)

    w(tmp_path, "agents/builder.md", agent_md(body="step 4: done"))
    findings = budget.check_placeholders(tmp_path)
    assert not findings


def test_no_mandate_language(tmp_path):
    w(tmp_path, "agents/builder.md", agent_md(body="You MUST always verify."))
    findings = budget.check_mandate_language(tmp_path)
    assert any(f.rule == "no-mandate-language" for f in findings)

    w(tmp_path, "agents/builder.md", agent_md(body="Verify before continuing."))
    findings = budget.check_mandate_language(tmp_path)
    assert not findings


def test_hard_requirements_heading(tmp_path):
    w(tmp_path, "agents/builder.md", agent_md(body="## HARD REQUIREMENTS\nfoo"))
    findings = budget.check_mandate_language(tmp_path)
    assert any(f.rule == "no-mandate-language" for f in findings)


def test_agent_tool_registry_missing_tool(tmp_path):
    w(tmp_path, "agents/builder.md", agent_md(name="builder", tools="Read, Write, Bash"))
    w(tmp_path, "docs/REGISTRY.md", "## builder\n- Read — baseline\n- Write — authors code\n")
    _, _, _, agents = budget.scan(tmp_path)
    findings = budget.check_registry(tmp_path, agents)
    assert any(f.rule == "agent-tool-registry" and "Bash" in f.detail for f in findings)


def test_agent_tool_registry_missing_file(tmp_path):
    w(tmp_path, "agents/builder.md", agent_md(name="builder", tools="Read"))
    _, _, _, agents = budget.scan(tmp_path)
    findings = budget.check_registry(tmp_path, agents)
    assert any(f.rule == "agent-tool-registry" and "missing" in f.detail for f in findings)


def test_reviewer_agent_no_write(tmp_path):
    w(tmp_path, "agents/reviewer.md", agent_md(name="reviewer", description="Reviews the diff", tools="Read, Write"))
    w(tmp_path, "docs/REGISTRY.md", "## reviewer\n- Read — baseline\n- Write — n/a\n")
    _, _, _, agents = budget.scan(tmp_path)
    findings = budget.check_registry(tmp_path, agents)
    assert any(f.rule == "reviewer-read-only" for f in findings)


def test_shell_selftest_missing(tmp_path):
    path = w(tmp_path, "tools/foo.sh", "#!/bin/sh\necho hi\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    findings = budget.check_shell_selftest(tmp_path)
    assert any(f.rule == "shell-selftest" and "no --selftest" in f.detail for f in findings)


def test_shell_selftest_pass(tmp_path):
    path = w(tmp_path, "tools/foo.sh", '#!/bin/sh\nif [ "$1" = "--selftest" ]; then exit 0; fi\necho hi\n')
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    findings = budget.check_shell_selftest(tmp_path)
    assert not findings


def test_shell_selftest_nonzero(tmp_path):
    path = w(tmp_path, "tools/foo.sh", '#!/bin/sh\nif [ "$1" = "--selftest" ]; then exit 1; fi\necho hi\n')
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    findings = budget.check_shell_selftest(tmp_path)
    assert any(f.rule == "shell-selftest" and "exited 1" in f.detail for f in findings)


def test_forbidden_write_path(tmp_path):
    w(tmp_path, "agents/builder.md", agent_md(body="Writes to .claude/settings.json when done."))
    findings = budget.check_forbidden_paths(tmp_path)
    assert any(f.rule == "no-forbidden-write-paths" for f in findings)

    w(tmp_path, "agents/builder.md", agent_md(body="Writes only inside the allowlist."))
    findings = budget.check_forbidden_paths(tmp_path)
    assert not findings


def test_report_generation(tmp_path):
    w(tmp_path, "agents/builder.md", agent_md(name="builder", description="short"))
    w(tmp_path, "docs/REGISTRY.md", "## builder\n- Read — baseline\n- Write — authors code\n")
    findings, rows, total = budget.gather_findings(tmp_path)
    budget.write_report(tmp_path, rows, total)
    report = (tmp_path / "docs" / "BUDGET.md").read_text()
    assert "Always-loaded frontmatter total" in report
    assert "agents/builder.md" in report


def test_report_splits_consuming_project_table(tmp_path):
    w(tmp_path, "agents/builder.md", agent_md(name="builder", description="short"))
    w(tmp_path, "docs/REGISTRY.md", "## builder\n- Read — baseline\n- Write — authors code\n")
    w(tmp_path, ".harness/architecture.md", "line\n")
    findings, rows, total = budget.gather_findings(tmp_path)
    budget.write_report(tmp_path, rows, total)
    report = (tmp_path / "docs" / "BUDGET.md").read_text()
    assert "## This repo" in report
    assert "## Templates for a consuming project" in report
    assert report.index("agents/builder.md") < report.index("## Templates for a consuming project")
    assert report.index("## Templates for a consuming project") < report.index(".harness/architecture.md")


def test_clean_repo_exits_zero(tmp_path):
    findings, *_ = budget.gather_findings(tmp_path)
    assert errs(findings) == []


def plugin_layout(tmp_path):
    w(tmp_path, "plugin/.claude-plugin/plugin.json", '{"name": "cairn", "version": "0.0.0"}')
    w(tmp_path, "docs/REGISTRY.md", "## builder\n- Read — baseline\n- Write — authors code\n")


def test_plugin_subfolder_caps_and_totals(tmp_path):
    plugin_layout(tmp_path)
    w(tmp_path, "plugin/agents/builder.md", agent_md(description="x" * 400))
    w(tmp_path, "plugin/commands/setup.md", "---\ndescription: dddd\n---\nbody\n")
    findings, rows, total = budget.gather_findings(tmp_path)
    assert any(f.rule == "agent-description" and f.path == "plugin/agents/builder.md" for f in errs(findings))
    assert total == 404


def test_plugin_subfolder_runtime_checks(tmp_path):
    plugin_layout(tmp_path)
    w(tmp_path, "plugin/agents/builder.md", agent_md(body="You MUST verify. <placeholder>"))
    w(tmp_path, "plugin/skills/foo/SKILL.md", "---\nname: foo\ndescription: d\n---\nno table\n")
    w(tmp_path, "plugin/skills/foo/reference/orphan.md", "content")
    rules = {f.rule for f in errs(budget.gather_findings(tmp_path)[0])}
    assert {"no-mandate-language", "no-placeholders", "reference-table-orphan"} <= rules


def test_root_agents_ignored_when_plugin_subfolder_exists(tmp_path):
    plugin_layout(tmp_path)
    w(tmp_path, "agents/builder.md", agent_md(description="x" * 400))
    _, _, total, agents = budget.scan(tmp_path)
    assert agents == [] and total == 0
