import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tasks  # noqa: E402

CAIRN_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class _Project:
    """A minimal `server.Project`-shaped stand-in (`.label`/`.root`) - kept
    local so this module has no import-time dependency on `server`."""

    label: str
    root: Path


@pytest.fixture(autouse=True)
def _no_real_gh(monkeypatch):
    """Every fixture project in this file lacks a `.harness/workflow.md`
    saying direct-commit, so `_done_fact` would otherwise shell out to the
    real `gh` binary on whatever machine runs this suite. Default to
    "gh not available" (mirrors §11's missing/unauthenticated fallback);
    a test that wants to exercise the real `gh`-parsing path overrides this
    locally with its own `monkeypatch.setattr(tasks.subprocess, "run", ...)`.
    """
    def _no_gh(*args, **kwargs):
        raise FileNotFoundError("gh not installed")

    monkeypatch.setattr(tasks.subprocess, "run", _no_gh)


def write_state(folder: Path, *, goal="a goal", key_info="in progress", flags="[]", extra_frontmatter="", body="- 2026-09-01: started.\n"):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "STATE.md").write_text(
        f"---\n"
        f"goal: {goal}\n"
        f"paths: [a.py]\n"
        f"done_when: it works\n"
        f"out_of_scope: []\n"
        f"source: \n"
        f"path: escalated\n"
        f"key_info: {key_info}\n"
        f"flags: {flags}\n"
        f"{extra_frontmatter}"
        f"---\n"
        f"> The frontmatter above is the state read on resume.\n\n"
        f"{body}"
    )


# --------------------------------------------------------------------------
# Frontmatter parsing
# --------------------------------------------------------------------------


def test_parse_frontmatter_reads_flat_scalars_and_flow_lists():
    text = (
        "---\n"
        "goal: Ship the thing\n"
        "paths: [a.py, b.py]\n"
        "key_info: awaiting requirements approval\n"
        "flags: []\n"
        "---\n"
        "body text\n"
    )
    fm = tasks.parse_frontmatter(text)
    assert fm["goal"] == "Ship the thing"
    assert fm["paths"] == ["a.py", "b.py"]
    assert fm["key_info"] == "awaiting requirements approval"
    assert fm["flags"] == []


def test_parse_frontmatter_reads_block_style_lists_and_quoted_flow_items_with_commas():
    text = (
        "---\n"
        "goal: g\n"
        "flags:\n"
        "  - first flag, with a comma\n"
        "  - second flag\n"
        'paths: ["a, b", "c"]\n'
        "---\n"
    )
    fm = tasks.parse_frontmatter(text)
    assert fm["flags"] == ["first flag, with a comma", "second flag"]
    assert fm["paths"] == ["a, b", "c"]


def test_parse_frontmatter_degrades_on_malformed_lines_instead_of_raising():
    text = (
        "---\n"
        "goal: g\n"
        "this line has no colon at all\n"
        "key_info: still readable\n"
        "---\n"
    )
    fm = tasks.parse_frontmatter(text)
    assert fm["goal"] == "g"
    assert fm["key_info"] == "still readable"


def test_parse_frontmatter_returns_empty_dict_when_no_frontmatter_block_exists():
    assert tasks.parse_frontmatter("just a plain markdown file\nno frontmatter here\n") == {}
    assert tasks.parse_frontmatter("---\nopens but never closes\n") == {}


def test_last_log_date_picks_the_last_dashed_date_line_and_ignores_the_blockquote():
    text = (
        "---\ngoal: g\n---\n"
        "> The frontmatter above is the state read on resume.\n\n"
        "- 2026-09-01: first entry.\n"
        "- 2026-09-15: second entry, latest.\n"
    )
    assert tasks._last_log_date(text) == "2026-09-15"


def test_last_log_date_is_none_when_no_dated_log_line_is_present():
    text = "---\ngoal: g\n---\nsome hand-edited body with no dated lines\n"
    assert tasks._last_log_date(text) is None


def test_last_log_datetime_parses_a_time_of_day_when_present():
    text = "---\ngoal: g\n---\n- 2026-09-15 14:30: did the thing.\n"
    assert tasks._last_log_datetime(text) == ("2026-09-15", "14:30")


def test_last_log_datetime_returns_empty_time_for_a_date_only_line_and_last_log_date_is_unaffected():
    text = "---\ngoal: g\n---\n- 2026-09-15: did the thing.\n"
    assert tasks._last_log_datetime(text) == ("2026-09-15", "")
    assert tasks._last_log_date(text) == "2026-09-15"


def test_last_log_datetime_reads_a_bare_timed_line():
    text = "---\ngoal: g\n---\n2026-09-23 14:05: did the thing.\n"
    assert tasks._last_log_datetime(text) == ("2026-09-23", "14:05")


def test_last_log_datetime_reads_a_bare_date_only_line():
    text = "---\ngoal: g\n---\n2026-09-23: did the thing.\n"
    assert tasks._last_log_datetime(text) == ("2026-09-23", "")


def test_last_log_datetime_keeps_the_first_day_of_a_bare_range():
    text = "---\ngoal: g\n---\n2026-09-28/29 10:00: spanned two days.\n"
    assert tasks._last_log_datetime(text) == ("2026-09-28", "10:00")


def test_last_log_datetime_returns_the_last_of_interleaved_bare_and_dashed_lines():
    text = (
        "---\ngoal: g\n---\n"
        "2026-09-20 08:00: bare first.\n"
        "- 2026-09-21 09:00: dashed second.\n"
        "2026-09-22: bare third, latest.\n"
    )
    assert tasks._last_log_datetime(text) == ("2026-09-22", "")


def test_last_log_datetime_ignores_a_bare_date_without_a_colon():
    text = "---\ngoal: g\n---\n2026-09-23 was a Tuesday.\n"
    assert tasks._last_log_datetime(text) is None


# --------------------------------------------------------------------------
# Activity-log parsing (§6.5)
# --------------------------------------------------------------------------


def test_parse_activity_splits_entries_skips_blockquote_and_drops_unparseable_lines():
    text = (
        "---\ngoal: g\n---\n"
        "> The frontmatter above is the state read on resume.\n\n"
        "- 2026-09-01: first entry.\n"
        "a hand-edited line matching neither pattern\n"
        "- 2026-09-15: second entry, latest.\n"
    )
    entries = tasks.parse_activity(text)
    assert entries == [
        {"date": "2026-09-01", "time": None, "text": "first entry."},
        {"date": "2026-09-15", "time": None, "text": "second entry, latest."},
    ]


def test_parse_activity_accepts_a_date_range_prefix_and_drops_a_stray_continuation_line():
    text = (
        "---\ngoal: g\n---\n"
        "- 2026-09-27/28: a real entry, always written as one dense line here.\n"
        "  a stray hand-wrapped continuation line, matching neither pattern.\n"
        "- 2026-09-29: next entry.\n"
    )
    entries = tasks.parse_activity(text)
    assert entries == [
        {"date": "2026-09-27/28", "time": None, "text": "a real entry, always written as one dense line here."},
        {"date": "2026-09-29", "time": None, "text": "next entry."},
    ]


def test_parse_activity_empty_when_there_is_no_body_after_frontmatter():
    assert tasks.parse_activity("---\ngoal: g\n---\n") == []


def test_parse_activity_consumes_a_time_of_day_without_leaking_it_into_text():
    text = "---\ngoal: g\n---\n- 2026-09-28 09:15: did X.\n"
    entries = tasks.parse_activity(text)
    assert entries == [{"date": "2026-09-28", "time": "09:15", "text": "did X."}]


def test_parse_activity_reads_bare_dated_lines_as_older_task_folders_write_them():
    """Older folders log bare `YYYY-MM-DD[ HH:MM]:` lines, and some carry a
    stray `---` after the frontmatter; every dated line still counts."""
    text = (
        "---\ngoal: g\n---\n"
        "> The frontmatter above is the state read on resume.\n"
        "---\n\n"
        "2026-09-23: first.\n"
        "2026-09-23 14:05: second.\n"
        "2026-09-24/25: range.\n"
    )
    entries = tasks.parse_activity(text)
    assert entries == [
        {"date": "2026-09-23", "time": None, "text": "first."},
        {"date": "2026-09-23", "time": "14:05", "text": "second."},
        {"date": "2026-09-24/25", "time": None, "text": "range."},
    ]


def test_parse_activity_drops_a_bare_date_line_without_its_colon():
    text = "---\ngoal: g\n---\n2026-09-23 was a Tuesday\n2026-09-23 14:05 no colon either\n"
    assert tasks.parse_activity(text) == []


def test_parse_activity_keeps_file_order_across_interleaved_bare_and_dashed_lines():
    text = (
        "---\ngoal: g\n---\n"
        "2026-09-20: bare one.\n"
        "- 2026-09-21 08:00: dashed one.\n"
        "2026-09-22 09:30: bare two.\n"
        "- 2026-09-23: dashed two.\n"
    )
    entries = tasks.parse_activity(text)
    assert [(e["date"], e["time"], e["text"]) for e in entries] == [
        ("2026-09-20", None, "bare one."),
        ("2026-09-21", "08:00", "dashed one."),
        ("2026-09-22", "09:30", "bare two."),
        ("2026-09-23", None, "dashed two."),
    ]


def test_parse_activity_against_this_repos_own_real_multi_entry_state_md():
    """The parent kanban-board task folder's own `STATE.md` (21 real dated
    entries as of this build, per requirements.md's own real-fixture
    instruction) - not just a short synthetic file."""
    real_state = CAIRN_ROOT / "docs/tasks/2026-09-28-1345-build-kanban-board/STATE.md"
    text = real_state.read_text()

    entries = tasks.parse_activity(text)

    assert len(entries) >= 20
    assert all(entry["date"] for entry in entries)
    assert entries[0]["date"] == "2026-09-28"
    assert entries[0]["text"].startswith("Created at the user's request")
    # The template's own blockquote line is real text in this file and must
    # never be mistaken for an entry.
    assert not any("frontmatter above is the state read on resume" in e["text"] for e in entries)


# --------------------------------------------------------------------------
# Discovery (§6.1)
# --------------------------------------------------------------------------


def test_iter_task_dirs_finds_state_and_draft_excludes_template(tmp_path):
    write_state(tmp_path / "docs/tasks/2026-01-01-0000-build-a")
    (tmp_path / "docs/tasks/2026-01-02-0000-review-b").mkdir(parents=True)
    (tmp_path / "docs/tasks/2026-01-02-0000-review-b/DRAFT.md").write_text("# Review\nStatus: pending\n")
    write_state(tmp_path / "docs/tasks/_template")

    found = {d.name: p.name for d, p in tasks._iter_task_dirs(tmp_path)}
    assert found == {"2026-01-01-0000-build-a": "STATE.md", "2026-01-02-0000-review-b": "DRAFT.md"}


def test_iter_task_dirs_prefers_state_over_draft_when_both_exist(tmp_path):
    folder = tmp_path / "docs/tasks/2026-01-01-0000-build-a"
    write_state(folder)
    (folder / "DRAFT.md").write_text("stray draft\n")

    found = list(tasks._iter_task_dirs(tmp_path))
    assert len(found) == 1
    assert found[0][1].name == "STATE.md"


def test_iter_task_dirs_yields_nothing_when_docs_tasks_is_absent(tmp_path):
    assert list(tasks._iter_task_dirs(tmp_path)) == []


def test_folder_kind_defaults_to_build_for_unrecognized_names():
    assert tasks._folder_kind("2026-01-01-0000-research-x") == "research"
    assert tasks._folder_kind("01-review-x") == "review"
    assert tasks._folder_kind("01-backend-tasks-api") == "build"
    assert tasks._folder_kind("2026-09-11-0759-portfolio-interview-docs") == "build"


def test_parent_relpath_detects_a_sub_task_one_level_up(tmp_path):
    parent = tmp_path / "docs/tasks/2026-01-01-0000-build-parent"
    write_state(parent)
    child = parent / "01-backend-tasks-api"
    write_state(child)

    assert tasks._parent_relpath(child, tmp_path) == "docs/tasks/2026-01-01-0000-build-parent"
    assert tasks._parent_relpath(parent, tmp_path) is None


# --------------------------------------------------------------------------
# §6.2 raw facts + precedence
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key_info,expected",
    [
        ("needs-human: which db to use?", True),
        ("stalled after 3 attempts", True),
        ("awaiting requirements approval", False),
        ("awaiting plan approval", False),
        ("Done. Reviewed PASS.", False),
        ("", False),
    ],
)
def test_needs_attention_fact_matches_only_needs_human_and_stalled(key_info, expected):
    assert tasks._needs_attention_fact(key_info) is expected


def test_awaiting_approval_fact_matches_both_gate_strings():
    assert tasks._awaiting_approval_fact("awaiting requirements approval") is True
    assert tasks._awaiting_approval_fact("awaiting plan approval") is True
    assert tasks._awaiting_approval_fact("approved; next: builder") is False
    assert tasks._awaiting_approval_fact("") is False


def test_is_direct_commit_project_reads_this_repos_own_workflow_md():
    assert tasks._is_direct_commit_project(CAIRN_ROOT / ".harness" / "workflow.md") is True


def test_is_direct_commit_project_false_when_branching_section_or_file_is_absent(tmp_path):
    assert tasks._is_direct_commit_project(tmp_path / "no-such-file.md") is False

    workflow = tmp_path / "workflow.md"
    workflow.write_text("## Gates\n- pytest\n")
    assert tasks._is_direct_commit_project(workflow) is False


def test_done_fact_research_kind_never_shells_out_to_gh(tmp_path, monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("gh should never be invoked for a research-kind folder")

    monkeypatch.setattr(tasks.subprocess, "run", _boom)
    assert tasks._done_fact("research", "Done.", "folder", tmp_path, {}, 60.0) is True
    assert tasks._done_fact("research", "still going", "folder", tmp_path, {}, 60.0) is False


def test_done_fact_direct_commit_project_skips_gh_and_reads_key_info(tmp_path, monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("gh should never be invoked for a direct-commit project")

    monkeypatch.setattr(tasks.subprocess, "run", _boom)
    (tmp_path / ".harness").mkdir()
    (tmp_path / ".harness" / "workflow.md").write_text("## Branching\n- Direct commits to main, no feature branches\n")

    assert tasks._done_fact("build", "Done, closed out.", "folder", tmp_path, {}, 60.0) is True
    assert tasks._done_fact("build", "still going", "folder", tmp_path, {}, 60.0) is False


def _fake_gh_result(returncode=0, stdout="0"):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def test_gh_pr_merged_parses_0_and_1_and_caches_within_ttl(tmp_path, monkeypatch):
    calls = []

    def _fake_run(args, **kwargs):
        calls.append(args)
        return _fake_gh_result(stdout="1")

    monkeypatch.setattr(tasks.subprocess, "run", _fake_run)
    cache = {}
    assert tasks._gh_pr_merged("my-folder", tmp_path, cache, 60.0) is True
    assert tasks._gh_pr_merged("my-folder", tmp_path, cache, 60.0) is True
    assert len(calls) == 1  # second call served from cache, no second subprocess

    calls.clear()
    assert tasks._gh_pr_merged("other-folder", tmp_path, cache, 60.0) is True
    assert len(calls) == 1  # different cache key, not served from "my-folder"'s entry


def test_gh_pr_merged_falls_back_to_none_on_non_0_1_output_or_nonzero_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(tasks.subprocess, "run", lambda *a, **k: _fake_gh_result(stdout="not-a-number"))
    assert tasks._gh_pr_merged("f", tmp_path, {}, 60.0) is None

    monkeypatch.setattr(tasks.subprocess, "run", lambda *a, **k: _fake_gh_result(returncode=1, stdout=""))
    assert tasks._gh_pr_merged("f", tmp_path, {}, 60.0) is None


def test_gh_pr_merged_falls_back_to_none_when_gh_is_missing(tmp_path, monkeypatch):
    def _missing(*args, **kwargs):
        raise FileNotFoundError("no gh")

    monkeypatch.setattr(tasks.subprocess, "run", _missing)
    assert tasks._gh_pr_merged("f", tmp_path, {}, 60.0) is None


def _stage(key_info="", *, kind="build", has_plan=True, done=False, active=False):
    return tasks._column(kind=kind, key_info=key_info, has_plan=has_plan, done=done, active=active)


def test_review_folder_sits_in_review_without_a_plan():
    assert _stage("round 1 drafted, awaiting Post or Edit", kind="review", has_plan=False) == "in_review"
    assert _stage("done: approved", kind="review", has_plan=False, done=True) == "done"
    assert _stage("blocked on author", kind="review", has_plan=False) == "blocked"


def test_column_precedence_across_the_seven_stages():
    assert _stage(done=True, key_info="awaiting plan approval", has_plan=False) == "done"
    assert _stage("awaiting plan approval", has_plan=False) == "awaiting_approval"
    assert _stage("awaiting requirements approval") == "awaiting_approval"
    assert _stage("plain", has_plan=False) == "scoping"
    assert _stage("plain", kind="research") == "scoping"
    assert _stage("reviewer running", active=True) == "in_review"
    assert _stage("approved; next: builder") == "planned"
    assert _stage("approved; next: builder", active=True) == "building"
    assert _stage("implementing step 2") == "building"
    assert _stage("blocked on X") == "blocked"
    assert _stage("Blocked: waiting") == "blocked"
    assert _stage("blocked on X", has_plan=False) == "blocked"
    assert _stage("blocked", kind="research") == "blocked"
    assert _stage("awaiting plan approval blocked") == "blocked"
    assert _stage("blocked", done=True) == "done"
    assert _stage("blocked", active=True) == "blocked"
    assert _stage("unblocked, reviewer running") == "in_review"
    assert _stage("reviewer blocked") == "blocked"


# --------------------------------------------------------------------------
# §8: the `active` heartbeat read
# --------------------------------------------------------------------------


def test_active_heartbeats_counts_a_marker_and_expires_one_past_the_ceiling(tmp_path):
    heartbeat_dir = tmp_path / "active"
    heartbeat_dir.mkdir()
    now = time.time()

    fresh = heartbeat_dir / "sess--agent1.active"
    fresh.write_text('{"project": "/repo", "task": "docs/tasks/x"}')
    old_but_live = heartbeat_dir / "sess--agent2.active"
    old_but_live.write_text('{"project": "/repo", "task": "docs/tasks/z"}')
    os.utime(old_but_live, (now - 3600, now - 3600))  # long-running, under the ceiling
    dead = heartbeat_dir / "sess--agent3.active"
    dead.write_text('{"project": "/repo", "task": "docs/tasks/y"}')
    past = now - tasks.MARKER_MAX_AGE_SECONDS - 60
    os.utime(dead, (past, past))

    live = tasks._active_heartbeats(heartbeat_dir, now=now)
    assert ("/repo", "docs/tasks/x") in live
    assert ("/repo", "docs/tasks/z") in live
    assert ("/repo", "docs/tasks/y") not in live


def test_active_heartbeats_ignores_a_session_pointer_alone(tmp_path):
    heartbeat_dir = tmp_path / "active"
    heartbeat_dir.mkdir()
    (heartbeat_dir / "sess.json").write_text('{"project": "/repo", "task": "docs/tasks/x"}')

    assert tasks._active_heartbeats(heartbeat_dir, now=time.time()) == set()


def test_active_heartbeats_two_markers_on_different_tasks_are_both_live(tmp_path):
    heartbeat_dir = tmp_path / "active"
    heartbeat_dir.mkdir()
    (heartbeat_dir / "s1--a.active").write_text('{"project": "/repo", "task": "docs/tasks/x"}')
    (heartbeat_dir / "s2--b.active").write_text('{"project": "/repo", "task": "docs/tasks/y"}')

    live = tasks._active_heartbeats(heartbeat_dir, now=time.time())
    assert live == {("/repo", "docs/tasks/x"), ("/repo", "docs/tasks/y")}


def test_active_heartbeats_ignores_corrupt_and_missing_directory(tmp_path):
    assert tasks._active_heartbeats(tmp_path / "nonexistent", now=time.time()) == set()

    heartbeat_dir = tmp_path / "active"
    heartbeat_dir.mkdir()
    (heartbeat_dir / "s--bad.active").write_text("not json at all")
    (heartbeat_dir / "s--wrong-shape.active").write_text('["not", "a", "dict"]')

    assert tasks._active_heartbeats(heartbeat_dir, now=time.time()) == set()


# --------------------------------------------------------------------------
# `build_cards` (§6.1-6.4, §9)
# --------------------------------------------------------------------------


def test_build_cards_stages_a_planned_a_needs_attention_and_an_active_card(tmp_path):
    # `Project.root` is contractually already-resolved (`server.discover_projects`
    # always does so) - resolving it here too, rather than relying on `tmp_path`
    # happening to already be canonical, keeps the heartbeat-match test honest.
    root = (tmp_path / "proj").resolve()
    write_state(root / "docs/tasks/2026-01-01-0000-build-ready", key_info="approved; next: builder")
    write_state(root / "docs/tasks/2026-01-02-0000-build-stuck", key_info="needs-human: pick a name")
    write_state(root / "docs/tasks/2026-01-03-0000-build-live", key_info="in progress")
    for n, name in enumerate(("ready", "stuck", "live"), start=1):
        (root / f"docs/tasks/2026-01-0{n}-0000-build-{name}" / "PLAN.md").write_text("plan\n")

    heartbeat_dir = tmp_path / "active"
    heartbeat_dir.mkdir()
    (heartbeat_dir / "s1--a.active").write_text(
        '{"project": "%s", "task": "docs/tasks/2026-01-03-0000-build-live"}' % str(root)
    )

    cards = tasks.build_cards([_Project("proj", root)], heartbeat_dir=heartbeat_dir)
    by_folder = {c["folder"]: c for c in cards}

    assert by_folder["docs/tasks/2026-01-01-0000-build-ready"]["column"] == "planned"
    stuck = by_folder["docs/tasks/2026-01-02-0000-build-stuck"]
    assert stuck["column"] == "building"  # keeps its stage; only the flag is set
    assert stuck["needs_attention"] is True
    assert by_folder["docs/tasks/2026-01-03-0000-build-live"]["column"] == "building"
    assert by_folder["docs/tasks/2026-01-03-0000-build-live"]["active"] is True
    assert all(c["sub_tasks"] is None for c in cards)


def test_build_cards_two_sibling_sub_tasks_report_independent_columns_and_parent_sits_in_parent_tasks(tmp_path):
    root = tmp_path / "proj"
    parent = root / "docs/tasks/2026-01-01-0000-build-parent"
    write_state(parent, key_info="in progress")
    write_state(parent / "01-first", key_info="Done, closed.")
    write_state(parent / "02-second", key_info="needs-human: which approach?")

    (root / ".harness").mkdir(parents=True)
    (root / ".harness" / "workflow.md").write_text("## Branching\n- Direct commits to main, no feature branches\n")

    cards = tasks.build_cards([_Project("proj", root)])
    by_folder = {c["folder"]: c for c in cards}

    first = by_folder["docs/tasks/2026-01-01-0000-build-parent/01-first"]
    second = by_folder["docs/tasks/2026-01-01-0000-build-parent/02-second"]
    assert first["column"] == "done"
    assert second["column"] == "scoping"  # no PLAN.md; keeps its stage
    assert second["needs_attention"] is True
    assert first["parent"] == "docs/tasks/2026-01-01-0000-build-parent"
    assert second["parent"] == "docs/tasks/2026-01-01-0000-build-parent"

    parent_card = by_folder["docs/tasks/2026-01-01-0000-build-parent"]
    assert parent_card["sub_tasks"] == {"done": 1, "total": 2}
    assert parent_card["column"] == "parent_tasks"  # one child not done: children decide, not the parent's own facts


def test_build_cards_omits_sub_tasks_field_for_a_folder_with_no_children(tmp_path):
    root = tmp_path / "proj"
    write_state(root / "docs/tasks/2026-01-01-0000-build-solo")

    cards = tasks.build_cards([_Project("proj", root)])
    assert cards[0]["sub_tasks"] is None


def test_build_cards_orders_most_recently_touched_first_using_same_day_times(tmp_path):
    root = tmp_path / "proj"
    write_state(root / "docs/tasks/2026-01-01-0000-build-earlier", body="- 2026-09-15 09:00: started.\n")
    write_state(root / "docs/tasks/2026-01-02-0000-build-later", body="- 2026-09-15 14:30: continued.\n")

    cards = tasks.build_cards([_Project("proj", root)])

    assert [c["folder"] for c in cards] == [
        "docs/tasks/2026-01-02-0000-build-later",
        "docs/tasks/2026-01-01-0000-build-earlier",
    ]
    assert "_sort_key" not in cards[0]


def test_build_cards_a_timed_touch_outranks_a_same_day_date_only_touch(tmp_path):
    root = tmp_path / "proj"
    write_state(root / "docs/tasks/2026-01-01-0000-build-no-time", body="- 2026-09-15: started.\n")
    write_state(root / "docs/tasks/2026-01-02-0000-build-with-time", body="- 2026-09-15 00:01: continued.\n")

    cards = tasks.build_cards([_Project("proj", root)])

    assert [c["folder"] for c in cards] == [
        "docs/tasks/2026-01-02-0000-build-with-time",
        "docs/tasks/2026-01-01-0000-build-no-time",
    ]


def test_build_cards_returns_last_log_time_from_a_timed_last_line(tmp_path):
    root = tmp_path / "proj"
    write_state(root / "docs/tasks/2026-01-01-0000-build-timed", body="- 2026-09-15 14:30: continued.\n")

    cards = tasks.build_cards([_Project("proj", root)])

    assert cards[0]["last_log_date"] == "2026-09-15"
    assert cards[0]["last_log_time"] == "14:30"


def test_build_cards_returns_empty_last_log_time_for_a_date_only_last_line(tmp_path):
    root = tmp_path / "proj"
    write_state(root / "docs/tasks/2026-01-01-0000-build-untimed", body="- 2026-09-15: started.\n")

    cards = tasks.build_cards([_Project("proj", root)])

    assert cards[0]["last_log_time"] == ""


def test_build_cards_reads_date_and_time_from_a_bare_timed_last_line(tmp_path):
    root = tmp_path / "proj"
    write_state(root / "docs/tasks/2026-01-01-0000-build-bare", body="2026-09-23 14:05: continued.\n")

    cards = tasks.build_cards([_Project("proj", root)])

    assert cards[0]["last_log_date"] == "2026-09-23"
    assert cards[0]["last_log_time"] == "14:05"


def test_build_cards_handles_a_review_folder_with_only_a_draft_md(tmp_path):
    root = tmp_path / "proj"
    folder = root / "docs/tasks/2026-01-05-0000-review-org-repo-pr-9"
    folder.mkdir(parents=True)
    (folder / "DRAFT.md").write_text("# PR #9 — Fix the thing (org/repo)\n\nStatus: pending user review\n")

    cards = tasks.build_cards([_Project("proj", root)])
    assert len(cards) == 1
    card = cards[0]
    assert card["kind"] == "review"
    assert card["goal"] == "PR #9 — Fix the thing (org/repo)"
    assert card["key_info"] == "Status: pending user review"
    assert card["last_log_date"] == "2026-01-05"


def test_build_cards_project_with_no_docs_tasks_and_only_template_never_errors(tmp_path):
    empty_root = tmp_path / "empty-proj"
    empty_root.mkdir()

    template_root = tmp_path / "template-only-proj"
    write_state(template_root / "docs/tasks/_template")

    cards = tasks.build_cards([_Project("empty", empty_root), _Project("templated", template_root)])
    assert cards == []


def test_build_cards_against_this_repos_own_real_task_folder(tmp_path):
    """`docs/tasks/2026-09-11-0759-portfolio-interview-docs/` (per
    requirements.md's own real-fixture constraint) is a long-closed-out
    folder whose retroactively-added `STATE.md` never changes: `key_info`
    reads "Done. ..." (whole-word `done`, precedence's second bucket), its
    name predates the `<kind>` convention (falls back to `build`), and its
    one log line is bare (`2026-09-25: ...`, no `- ` prefix), which is now
    read as a log line, so `last_log_date` is that line's date."""
    heartbeat_dir = tmp_path / "active"  # empty: nothing in this repo is "live" for this test

    cards = tasks.build_cards([_Project("cairn-2.0", CAIRN_ROOT)], heartbeat_dir=heartbeat_dir)
    by_folder = {c["folder"]: c for c in cards}

    folder = "docs/tasks/2026-09-11-0759-portfolio-interview-docs"
    assert folder in by_folder
    card = by_folder[folder]
    assert card["kind"] == "build"
    assert card["parent"] is None
    assert card["done"] is True
    assert card["needs_attention"] is False
    assert card["column"] == "done"
    assert card["last_log_date"] == "2026-09-25"


def test_build_cards_two_real_sibling_sub_tasks_report_different_columns(tmp_path):
    """`docs/tasks/2026-09-25-0615-research-aihero-skills-comparison/`'s two
    real, long-closed sub-tasks (both `key_info: Done. ...`) independently
    verify §6.2's precedence against real fixture data, per
    requirements.md's Success criteria and `../PRD.md` §13."""
    heartbeat_dir = tmp_path / "active"

    cards = tasks.build_cards([_Project("cairn-2.0", CAIRN_ROOT)], heartbeat_dir=heartbeat_dir)
    by_folder = {c["folder"]: c for c in cards}

    parent = "docs/tasks/2026-09-25-0615-research-aihero-skills-comparison"
    first = by_folder[f"{parent}/01-build-add-triage-skill"]
    second = by_folder[f"{parent}/02-build-fold-tdd-into-builder"]
    assert first["column"] == "done"
    assert second["column"] == "done"
    assert first["parent"] == parent
    assert second["parent"] == parent
    assert by_folder[parent]["sub_tasks"] == {"done": 2, "total": 2}
    assert by_folder[parent]["column"] == "done"


# --------------------------------------------------------------------------
# Docs listing (§6.6) and `build_detail` (§6.5, §9)
# --------------------------------------------------------------------------


def test_list_docs_excludes_state_and_draft_and_is_not_recursive(tmp_path):
    folder = tmp_path / "a-task"
    write_state(folder)
    (folder / "REQUIREMENTS.md").write_text("reqs\n")
    (folder / "PRD.md").write_text("prd\n")
    (folder / "wireframes").mkdir()
    (folder / "wireframes" / "nested.md").write_text("nested, not a doc\n")

    docs = tasks._list_docs(folder)
    names = {d["name"] for d in docs}
    assert names == {"REQUIREMENTS.md", "PRD.md"}
    assert all(isinstance(d["size"], int) and d["size"] > 0 for d in docs)
    assert all(d["modified"] for d in docs)


def test_list_docs_shows_draft_when_state_md_is_the_details_source(tmp_path):
    folder = tmp_path / "2026-10-07-0700-review-org-repo-pr-9"
    write_state(folder, key_info="round 1 posted, awaiting author")
    (folder / "DRAFT.md").write_text("# PR #9 — Fix the thing\n")
    assert {d["name"] for d in tasks._list_docs(folder)} == {"DRAFT.md"}


def test_list_docs_hides_draft_when_it_is_the_details_source(tmp_path):
    folder = tmp_path / "2026-10-07-0700-review-org-repo-pr-9"
    folder.mkdir()
    (folder / "DRAFT.md").write_text("# PR #9 — Fix the thing\n")
    (folder / "notes.md").write_text("notes\n")
    assert {d["name"] for d in tasks._list_docs(folder)} == {"notes.md"}


def test_build_detail_returns_none_for_a_folder_with_no_state_or_draft(tmp_path):
    folder = tmp_path / "not-a-task-folder"
    folder.mkdir()
    assert tasks.build_detail(_Project("proj", tmp_path), folder) is None


def test_build_detail_assembles_frontmatter_activity_and_docs_for_a_state_folder(tmp_path):
    root = tmp_path / "proj"
    folder = root / "docs/tasks/2026-01-01-0000-build-a"
    write_state(folder, goal="Ship it", key_info="in progress", body="- 2026-01-01: started.\n- 2026-01-02: continued.\n")
    (folder / "REQUIREMENTS.md").write_text("reqs\n")

    detail = tasks.build_detail(_Project("proj", root), folder)

    assert detail["frontmatter"]["goal"] == "Ship it"
    assert detail["activity"] == [
        {"date": "2026-01-01", "time": None, "text": "started."},
        {"date": "2026-01-02", "time": None, "text": "continued."},
    ]
    assert detail["draft_content"] is None
    assert detail["sub_tasks"] is None
    assert [d["name"] for d in detail["docs"]] == ["REQUIREMENTS.md"]
    assert detail["column"] == "scoping"
    assert detail["needs_attention"] is False
    assert detail["active"] is False


def test_build_detail_review_folder_carries_draft_content_not_activity(tmp_path):
    root = tmp_path / "proj"
    folder = root / "docs/tasks/2026-01-05-0000-review-org-repo-pr-9"
    folder.mkdir(parents=True)
    (folder / "DRAFT.md").write_text("# PR #9 — Fix the thing\n\nStatus: pending user review\n")

    detail = tasks.build_detail(_Project("proj", root), folder)

    assert detail["activity"] is None
    assert detail["draft_content"] == (folder / "DRAFT.md").read_text()
    assert detail["frontmatter"] == {"goal": "PR #9 — Fix the thing", "key_info": "Status: pending user review"}


def test_list_docs_against_this_repos_own_real_task_folder_with_multiple_loose_docs():
    """The parent kanban-board task folder's own real loose docs
    (REQUIREMENTS.md/PRODUCT-BRIEF.md/PRD.md/ROADMAP.md, per requirements.md's
    own Success criteria) - not a synthetic fixture."""
    folder = CAIRN_ROOT / "docs/tasks/2026-09-28-1345-build-kanban-board"
    docs = tasks._list_docs(folder)
    names = {d["name"] for d in docs}
    assert {"REQUIREMENTS.md", "PRODUCT-BRIEF.md", "PRD.md", "ROADMAP.md"}.issubset(names)
    assert "STATE.md" not in names


def test_build_detail_lists_full_sub_task_records_for_a_parent(tmp_path):
    root = tmp_path / "proj"
    parent = root / "docs/tasks/2026-01-01-0000-build-parent"
    write_state(parent, goal="parent goal")
    write_state(parent / "01-first", goal="first sub-task", key_info="Done, closed.")
    write_state(parent / "02-second", goal="second sub-task", key_info="needs-human: which way?")

    (root / ".harness").mkdir()
    (root / ".harness" / "workflow.md").write_text("## Branching\n- Direct commits to main, no feature branches\n")

    detail = tasks.build_detail(_Project("proj", root), parent)

    assert detail["sub_tasks"] == [
        {
            "folder": "docs/tasks/2026-01-01-0000-build-parent/01-first",
            "column": "done",
            "needs_attention": False,
            "active": False,
            "goal": "first sub-task",
        },
        {
            "folder": "docs/tasks/2026-01-01-0000-build-parent/02-second",
            "column": "scoping",
            "needs_attention": True,
            "active": False,
            "goal": "second sub-task",
        },
    ]


def test_build_cards_derives_each_stage_from_folder_contents_and_key_info(tmp_path):
    root = (tmp_path / "proj").resolve()
    (root / ".harness").mkdir(parents=True)
    (root / ".harness" / "workflow.md").write_text("## Branching\n- Direct commits to main, no feature branches\n")
    tasks_dir = root / "docs/tasks"
    cases = {
        "2026-01-01-0000-build-a": ("plain", False, "scoping"),
        "2026-01-02-0000-build-b": ("awaiting plan approval", False, "awaiting_approval"),
        "2026-01-03-0000-build-c": ("awaiting plan approval", True, "awaiting_approval"),
        "2026-01-04-0000-research-d": ("plain", True, "scoping"),
        "2026-01-05-0000-research-e": ("Done, closed.", True, "done"),
        "2026-01-06-0000-build-f": ("reviewer running", True, "in_review"),
        "2026-01-07-0000-build-g": ("Done, closed.", True, "done"),
        "2026-01-08-0000-build-h": ("implementing step 2", True, "building"),
        "2026-01-09-0000-build-i": ("blocked on X", True, "blocked"),
        "2026-01-10-0000-build-j": ("unblocked", True, "building"),
    }
    for name, (key_info, plan, _) in cases.items():
        write_state(tasks_dir / name, key_info=key_info)
        if plan:
            (tasks_dir / name / "PLAN.md").write_text("plan\n")

    by_folder = {c["folder"]: c for c in tasks.build_cards([_Project("proj", root)])}
    for name, (_, _, expected) in cases.items():
        assert by_folder[f"docs/tasks/{name}"]["column"] == expected, name
    assert by_folder["docs/tasks/2026-01-02-0000-build-b"]["needs_attention"] is False
    assert by_folder["docs/tasks/2026-01-03-0000-build-c"]["needs_attention"] is False


def test_build_cards_needs_human_and_stalled_keep_stage_and_set_flag(tmp_path):
    root = (tmp_path / "proj").resolve()
    for name, ki in (("2026-01-01-0000-build-a", "needs-human: x"), ("2026-01-02-0000-build-b", "stalled: y")):
        write_state(root / "docs/tasks" / name, key_info=ki)
        (root / "docs/tasks" / name / "PLAN.md").write_text("plan\n")
    for c in tasks.build_cards([_Project("proj", root)]):
        assert c["needs_attention"] is True
        assert c["column"] == "building"


def test_build_cards_fresh_heartbeat_on_approved_plan_is_building_and_active(tmp_path):
    root = (tmp_path / "proj").resolve()
    folder = root / "docs/tasks/2026-01-01-0000-build-a"
    write_state(folder, key_info="approved; next: builder")
    (folder / "PLAN.md").write_text("plan\n")
    heartbeat_dir = tmp_path / "active"
    heartbeat_dir.mkdir()
    (heartbeat_dir / "s--a.active").write_text('{"project": "%s", "task": "docs/tasks/2026-01-01-0000-build-a"}' % str(root))

    card = tasks.build_cards([_Project("proj", root)], heartbeat_dir=heartbeat_dir)[0]
    assert card["column"] == "building"
    assert card["active"] is True


def test_build_cards_blocked_keeps_needs_attention_and_active_badges(tmp_path):
    root = (tmp_path / "proj").resolve()
    a = root / "docs/tasks/2026-01-01-0000-build-a"
    b = root / "docs/tasks/2026-01-02-0000-build-b"
    write_state(a, key_info="needs-human: blocked on X")
    write_state(b, key_info="blocked on Y")
    for f in (a, b):
        (f / "PLAN.md").write_text("plan\n")
    heartbeat_dir = tmp_path / "active"
    heartbeat_dir.mkdir()
    (heartbeat_dir / "s--a.active").write_text('{"project": "%s", "task": "docs/tasks/2026-01-02-0000-build-b"}' % str(root))

    by = {c["folder"].rsplit("/", 1)[1]: c for c in tasks.build_cards([_Project("proj", root)], heartbeat_dir=heartbeat_dir)}
    assert by["2026-01-01-0000-build-a"]["column"] == "blocked"
    assert by["2026-01-01-0000-build-a"]["needs_attention"] is True
    assert by["2026-01-02-0000-build-b"]["column"] == "blocked"
    assert by["2026-01-02-0000-build-b"]["active"] is True


def test_blocked_child_is_not_done_in_sub_task_counts_and_detail(tmp_path):
    root = (tmp_path / "proj").resolve()
    (root / ".harness").mkdir(parents=True)
    (root / ".harness" / "workflow.md").write_text("## Branching\n- Direct commits to main, no feature branches\n")
    parent = root / "docs/tasks/2026-01-01-0000-build-parent"
    write_state(parent, key_info="in progress")
    write_state(parent / "01-a", key_info="blocked on X")
    write_state(parent / "02-b", key_info="Done, closed.")

    cards = {c["folder"]: c for c in tasks.build_cards([_Project("proj", root)])}
    assert cards["docs/tasks/2026-01-01-0000-build-parent"]["sub_tasks"] == {"done": 1, "total": 2}
    detail = tasks.build_detail(_Project("proj", root), parent)
    subs = {e["folder"].rsplit("/", 1)[1]: e for e in detail["sub_tasks"]}
    assert subs["01-a"]["column"] == "blocked"
    assert subs["02-b"]["column"] == "done"


def test_build_detail_reports_needs_attention_and_active_per_folder_and_sub_task(tmp_path):
    root = (tmp_path / "proj").resolve()
    parent = root / "docs/tasks/2026-01-01-0000-build-parent"
    write_state(parent, key_info="needs-human: x")
    write_state(parent / "01-live", key_info="in progress")
    write_state(parent / "02-plain", key_info="in progress")
    heartbeat_dir = tmp_path / "active"
    heartbeat_dir.mkdir()
    (heartbeat_dir / "s--a.active").write_text(
        '{"project": "%s", "task": "docs/tasks/2026-01-01-0000-build-parent/01-live"}' % str(root)
    )

    detail = tasks.build_detail(_Project("proj", root), parent, heartbeat_dir=heartbeat_dir)
    assert detail["needs_attention"] is True
    assert detail["active"] is False
    subs = {e["folder"].rsplit("/", 1)[1]: e for e in detail["sub_tasks"]}
    assert (subs["01-live"]["needs_attention"], subs["01-live"]["active"]) == (False, True)
    assert (subs["02-plain"]["needs_attention"], subs["02-plain"]["active"]) == (False, False)
    assert all("column" in e for e in detail["sub_tasks"])


# --------------------------------------------------------------------------
# Parent-task rollup: a folder with sub-tasks sits in `parent_tasks` until
# every child is done, whatever its own facts say
# --------------------------------------------------------------------------

_PARENT = "docs/tasks/2026-01-01-0000-build-parent"


def _direct_commit_project(root: Path) -> None:
    (root / ".harness").mkdir(parents=True, exist_ok=True)
    (root / ".harness" / "workflow.md").write_text("## Branching\n- Direct commits to main, no feature branches\n")


def test_parent_with_done_word_and_merged_pr_stays_in_parent_tasks_while_a_child_is_not_done(tmp_path, monkeypatch):
    root = (tmp_path / "proj").resolve()
    parent = root / _PARENT
    write_state(parent, key_info="Sub-task 01 done; 02 building")
    (parent / "PLAN.md").write_text("plan\n")
    write_state(parent / "01-a", key_info="Done, closed.")
    write_state(parent / "02-b", key_info="implementing step 2")
    (parent / "02-b" / "PLAN.md").write_text("plan\n")

    def _fake_run(args, **kwargs):
        merged = "1" if args[:3] == ["gh", "pr", "list"] and args[4] == "2026-01-01-0000-build-parent" else "0"
        return _fake_gh_result(stdout=merged)

    monkeypatch.setattr(tasks.subprocess, "run", _fake_run)

    by_folder = {c["folder"]: c for c in tasks.build_cards([_Project("proj", root)])}
    assert by_folder[_PARENT]["column"] == "parent_tasks"
    assert by_folder[_PARENT]["done"] is False
    assert by_folder[f"{_PARENT}/02-b"]["column"] == "building"


def test_parent_is_done_once_every_child_is_done_whatever_its_own_key_info_says(tmp_path):
    root = (tmp_path / "proj").resolve()
    _direct_commit_project(root)
    parent = root / _PARENT
    write_state(parent, key_info="in progress")
    write_state(parent / "01-a", key_info="Done, closed.")
    write_state(parent / "02-b", key_info="Complete.")

    card = {c["folder"]: c for c in tasks.build_cards([_Project("proj", root)])}[_PARENT]
    assert card["column"] == "done"
    assert card["done"] is True
    assert card["sub_tasks"] == {"done": 2, "total": 2}


@pytest.mark.parametrize("key_info", ["blocked on X", "awaiting plan approval", "needs-human: blocked on X"])
def test_parent_blocked_or_awaiting_approval_still_sits_in_parent_tasks_and_keeps_its_attention_flag(tmp_path, key_info):
    root = (tmp_path / "proj").resolve()
    _direct_commit_project(root)
    parent = root / _PARENT
    write_state(parent, key_info=key_info)
    write_state(parent / "01-a", key_info="implementing")

    card = {c["folder"]: c for c in tasks.build_cards([_Project("proj", root)])}[_PARENT]
    assert card["column"] == "parent_tasks"
    assert card["needs_attention"] is key_info.startswith("needs-human")


def test_nested_parents_roll_up_deepest_first(tmp_path):
    root = (tmp_path / "proj").resolve()
    _direct_commit_project(root)
    parent = root / _PARENT
    write_state(parent, key_info="Done, closed.")
    write_state(parent / "01", key_info="Done, closed.")
    write_state(parent / "01" / "01-x", key_info="implementing")

    by_folder = {c["folder"]: c for c in tasks.build_cards([_Project("proj", root)])}
    assert by_folder[f"{_PARENT}/01"]["column"] == "parent_tasks"
    assert by_folder[_PARENT]["column"] == "parent_tasks"
    assert by_folder[_PARENT]["sub_tasks"] == {"done": 0, "total": 1}

    write_state(parent / "01" / "01-x", key_info="Done, closed.")
    by_folder = {c["folder"]: c for c in tasks.build_cards([_Project("proj", root)])}
    assert by_folder[f"{_PARENT}/01"]["column"] == "done"
    assert by_folder[_PARENT]["column"] == "done"
    assert by_folder[_PARENT]["sub_tasks"] == {"done": 1, "total": 1}


def test_build_detail_matches_the_board_for_a_parent_and_a_nested_child(tmp_path):
    root = (tmp_path / "proj").resolve()
    _direct_commit_project(root)
    parent = root / _PARENT
    write_state(parent, key_info="Done, closed.")
    write_state(parent / "01", key_info="Done, closed.")
    write_state(parent / "01" / "01-x", key_info="implementing")

    detail = tasks.build_detail(_Project("proj", root), parent)
    assert detail["column"] == "parent_tasks"
    assert [(e["folder"], e["column"]) for e in detail["sub_tasks"]] == [(f"{_PARENT}/01", "parent_tasks")]

    board = {c["folder"]: c["column"] for c in tasks.build_cards([_Project("proj", root)])}
    assert detail["column"] == board[_PARENT]
