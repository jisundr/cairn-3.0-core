#!/usr/bin/env python3
"""Task-folder discovery, frontmatter parsing, `§6.2` column precedence, the
parent-task rollup (a folder with sub-tasks sits in `parent_tasks` until every
child is done), and the `active` subagent-marker read for mission control's
kanban board. stdlib only.

Design: see `docs/tasks/2026-09-28-1345-build-kanban-board/PRD.md` §6.1-6.4,
§8 (read side only), §9 (`GET /api/tasks` response shape). Read-only against
every artifact this module touches - a `STATE.md`/`DRAFT.md` file, a
project's own `.harness/workflow.md`, and a subagent marker file under
`~/.claude/cairn/active/` are only ever read here, never written.

Callers pass in `Project`-shaped objects (a `.label: str` and a
`.root: Path`, matching `server.Project`) rather than this module importing
`server` itself, so `server.py` can import `tasks` without a cycle.
"""
import json
import re
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# A subagent marker (`<session_id>--<agent_id>.active`) is dead if its mtime
# is older than this many seconds (4 hours). Presence is the activity signal;
# this only guards markers a crashed subagent never removed. The
# `hooks/subagent-marker.sh` sweep uses the same ceiling.
MARKER_MAX_AGE_SECONDS = 14400

# `~/.claude/cairn/active/<session_id>--<agent_id>.active`, per §8 - mirrors
# `server.DEFAULT_KNOWN_PROJECTS_PATH`'s global-registry placement.
DEFAULT_HEARTBEAT_DIR = Path.home() / ".claude" / "cairn" / "active"

# `gh pr list` is a per-folder network+auth call (§14 Risk); cached
# in-process per `(project_root, folder_name)` for this long.
GH_CACHE_TTL_SECONDS = 60.0


# --------------------------------------------------------------------------
# Frontmatter: flat scalars + string lists, no PyYAML (`.harness/architecture.md`)
# --------------------------------------------------------------------------


def _frontmatter_bounds(lines: list[str]) -> tuple[int, int] | None:
    """`(start, end)` such that `lines[start:end]` is the frontmatter
    block's own lines, excluding both `---` delimiters - or `None` if the
    file doesn't open with `---`, or never closes it (degrade, not crash:
    callers treat `None` as "no frontmatter found")."""
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return (1, i)
    return None


_KEY_LINE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*):(.*)$")


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _split_flow_list(inner: str) -> list[str]:
    """Splits a `[a, b, c]` flow list's inner text on top-level commas only
    - a comma inside a quoted item (`["a, b", "c"]`) doesn't split it."""
    items: list[str] = []
    current: list[str] = []
    in_quotes = False
    quote_char = ""
    for ch in inner:
        if in_quotes:
            current.append(ch)
            if ch == quote_char:
                in_quotes = False
            continue
        if ch in "\"'":
            in_quotes = True
            quote_char = ch
            current.append(ch)
            continue
        if ch == ",":
            items.append("".join(current))
            current = []
            continue
        current.append(ch)
    items.append("".join(current))
    return items


def _parse_frontmatter_lines(lines: list[str]) -> dict[str, str | list[str]]:
    result: dict[str, str | list[str]] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for line in lines:
        if current_list is not None:
            stripped = line.strip()
            if stripped.startswith("- "):
                current_list.append(_strip_quotes(stripped[2:]))
                continue
            result[current_key] = current_list
            current_key, current_list = None, None
            # fall through: this line may itself be the next key

        match = _KEY_LINE_RE.match(line)
        if not match:
            continue  # unparseable line: dropped, not fatal (degrade)
        key, raw_value = match.group(1), match.group(2).strip()

        if raw_value == "":
            # Either a block list follows (`flags:\n  - a`) or the scalar
            # is genuinely empty - resolved once the next line is seen.
            current_key, current_list = key, []
            continue
        if raw_value.startswith("[") and raw_value.endswith("]"):
            inner = raw_value[1:-1].strip()
            result[key] = [] if inner == "" else [_strip_quotes(item) for item in _split_flow_list(inner)]
        else:
            result[key] = _strip_quotes(raw_value)

    if current_list is not None:
        result[current_key] = current_list
    return result


def parse_frontmatter(text: str) -> dict[str, str | list[str]]:
    """A `STATE.md`'s frontmatter block (flat scalars + string lists,
    `goal`/`paths`/`done_when`/`out_of_scope`/`source`/`path`/`key_info`/
    `flags`) as a dict. `text` is the whole file's content. `{}` if there's
    no well-formed opening+closing `---` pair - never raises on malformed
    content."""
    bounds = _frontmatter_bounds(text.splitlines())
    if bounds is None:
        return {}
    lines = text.splitlines()
    return _parse_frontmatter_lines(lines[bounds[0] : bounds[1]])


_LOG_DATE_RE = re.compile(
    r"^- (\d{4}-\d{2}-\d{2})(?: (\d{2}:\d{2}))?"
    r"|^(\d{4}-\d{2}-\d{2})(?:/\d{2})?(?: (\d{2}:\d{2}))?:",
    re.MULTILINE,
)


def _last_log_datetime(text: str) -> tuple[str, str] | None:
    """The last `(date, time)` pair starting a log line in `text`'s body
    (after the frontmatter's closing `---`, or the whole text if there's no
    frontmatter). A log line is either dashed (`- YYYY-MM-DD[ HH:MM]`) or
    bare (`YYYY-MM-DD[/DD][ HH:MM]:` - the colon is required, as in
    `_ACTIVITY_START_RE`, so prose that merely opens with a date is not
    read). A range keeps only its first day. `time` is `""` when that line
    carries no `HH:MM`. `None` if no dated line is found at all."""
    lines = text.splitlines()
    bounds = _frontmatter_bounds(lines)
    body_lines = lines[bounds[1] + 1 :] if bounds is not None else lines
    matches = list(_LOG_DATE_RE.finditer("\n".join(body_lines)))
    if not matches:
        return None
    dashed_date, dashed_time, bare_date, bare_time = matches[-1].groups()
    return dashed_date or bare_date, dashed_time or bare_time or ""


def _last_log_date(text: str) -> str | None:
    """The last `YYYY-MM-DD` date starting a dashed or bare log line in
    `text`'s body - `None` if no such line is found. A thin delegate to
    `_last_log_datetime` that drops the time-of-day."""
    result = _last_log_datetime(text)
    return result[0] if result else None


def _last_touched_sort_key(date: str, time: str) -> str:
    """A fixed-width `YYYY-MM-DD HH:MM` string, lexicographically sortable -
    `time` defaults to `"00:00"` (the earliest possible clock time for that
    day) when absent, so a date-only touch is deliberately the most
    conservative reading: it never outranks a same-day touch that did
    record a time."""
    return f"{date} {time or '00:00'}"


def _draft_summary(text: str) -> tuple[str, str]:
    """A `review` folder's `DRAFT.md` has no frontmatter - `/cairn-triage`
    step 1's own treatment ("one trailing line") is mirrored here for both
    ends: the first non-empty line (the draft's own title) stands in for
    `goal`, the last non-empty line stands in for `key_info`."""
    non_empty = [line.strip() for line in text.splitlines() if line.strip()]
    if not non_empty:
        return "", ""
    goal = non_empty[0].lstrip("#").strip()
    return goal, non_empty[-1]


_ACTIVITY_DATE = r"\d{4}-\d{2}-\d{2}(?:/\d{2})?"
_ACTIVITY_START_RE = re.compile(
    rf"^(?:- (?P<date>{_ACTIVITY_DATE})(?: (?P<time>\d{{2}}:\d{{2}}))?:?"
    rf"|(?P<bare_date>{_ACTIVITY_DATE})(?: (?P<bare_time>\d{{2}}:\d{{2}}))?:)\s*"
)


def parse_activity(text: str) -> list[dict]:
    """`STATE.md`'s append-only log, after its frontmatter, split into one
    timeline entry per dated line, in either of the two forms real task
    folders use: dashed (`- YYYY-MM-DD[ HH:MM][:]`) or bare
    (`YYYY-MM-DD[ HH:MM]:`, where the trailing colon is required so a prose
    line that merely starts with a date is not taken for an entry). A
    `YYYY-MM-DD/DD` date-range prefix is also recognized (§6.5). Each entry
    is `{date, time, text}`, `time` being the line's `HH:MM` or None when it
    has none. Every real entry in this repo is written as one dense line,
    never soft-wrapped, so an entry's text is exactly that line's own
    content after its dated prefix; a line in neither form - the `cairn:shared`-template blockquote that precedes
    the first entry, a blank separator line, or hand-edited stray content -
    is dropped outright rather than folded into whichever entry precedes
    it, and never errors the whole parse (`pricing.py`/`parser.py`'s own
    degrade-not-crash convention)."""
    lines = text.splitlines()
    bounds = _frontmatter_bounds(lines)
    body_lines = lines[bounds[1] + 1 :] if bounds is not None else lines

    entries: list[dict] = []
    for line in body_lines:
        match = _ACTIVITY_START_RE.match(line)
        if match:
            entries.append(
                {
                    "date": match.group("date") or match.group("bare_date"),
                    "time": match.group("time") or match.group("bare_time"),
                    "text": line[match.end() :].strip(),
                }
            )
        # else: dropped - either precedes the first entry (blockquote/blank)
        # or is unparseable stray content, per §6.5.
    return entries


_FOLDER_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def _folder_name_date(folder_dir: Path, tasks_root: Path) -> str:
    """Walks from `folder_dir` up to (excluding) `tasks_root` looking for
    the nearest ancestor whose name is date-prefixed - a sub-task folder
    (`0N-<kind>-slug`) has no date of its own, so this finds its parent's.
    `""` if nothing in the chain is dated."""
    current = folder_dir
    while current != tasks_root:
        match = _FOLDER_DATE_RE.match(current.name)
        if match:
            return match.group(1)
        current = current.parent
    return ""


# --------------------------------------------------------------------------
# Discovery (§6.1)
# --------------------------------------------------------------------------

_KIND_RE = re.compile(r"^(?:\d{4}-\d{2}-\d{2}-\d{4}|\d{2})-(build|research|review)-")


def _folder_kind(folder_name: str) -> str:
    """`build`/`research`/`review` parsed from a `YYYY-MM-DD-HHMM-<kind>-
    slug` or `0N-<kind>-slug` folder name; `build` for anything else
    (folders predating the `<kind>` naming convention) - a reasonable
    default rather than an error, per this module's degrade-not-crash
    posture."""
    match = _KIND_RE.match(folder_name)
    return match.group(1) if match else "build"


def _parent_relpath(folder_dir: Path, project_root: Path) -> str | None:
    """The immediate parent folder's project-root-relative path, if that
    parent itself holds a `STATE.md`/`DRAFT.md` (§6.1's sub-task test) -
    `None` for a top-level folder (whose parent is `docs/tasks` itself)."""
    parent = folder_dir.parent
    if parent == project_root or not parent.is_relative_to(project_root):
        return None
    if (parent / "STATE.md").is_file() or (parent / "DRAFT.md").is_file():
        return parent.relative_to(project_root).as_posix()
    return None


def _iter_task_dirs(project_root: Path):
    """Yields `(folder_dir, source_path)` for every task folder under
    `project_root/docs/tasks/` - `source_path` is that folder's own
    `STATE.md`, or (only when no `STATE.md` exists there) its `DRAFT.md`,
    per §6.1. Any path with a `_template` segment is excluded. Nothing is
    yielded, without error, when `docs/tasks/` doesn't exist at all (§11)."""
    tasks_root = project_root / "docs" / "tasks"
    if not tasks_root.is_dir():
        return
    seen_dirs: set[Path] = set()
    for state_path in sorted(tasks_root.glob("**/STATE.md")):
        if "_template" in state_path.parts:
            continue
        seen_dirs.add(state_path.parent)
        yield state_path.parent, state_path
    for draft_path in sorted(tasks_root.glob("**/DRAFT.md")):
        if "_template" in draft_path.parts or draft_path.parent in seen_dirs:
            continue
        yield draft_path.parent, draft_path


# --------------------------------------------------------------------------
# §6.2 raw facts + precedence
# --------------------------------------------------------------------------

_NEEDS_ATTENTION_SUBSTRINGS = ("needs-human", "stalled")
_APPROVAL_SUBSTRINGS = ("awaiting requirements approval", "awaiting plan approval")


def _needs_attention_fact(key_info: str) -> bool:
    """Case-sensitive substring match on `needs-human`/`stalled` (an
    unattended-mode marker). An approval-gate string no longer counts: it
    has its own stage column (`awaiting_approval`)."""
    if not key_info:
        return False
    return any(s in key_info for s in _NEEDS_ATTENTION_SUBSTRINGS)


def _awaiting_approval_fact(key_info: str) -> bool:
    """Case-sensitive substring match on either approval-gate string."""
    if not key_info:
        return False
    return any(s in key_info for s in _APPROVAL_SUBSTRINGS)


_REVIEW_WORD_RE = re.compile(r"\b(review|reviewer)\b", re.IGNORECASE)


def _in_review_fact(key_info: str) -> bool:
    """Heuristic: `key_info` names review as a whole word."""
    return bool(_REVIEW_WORD_RE.search(key_info or ""))


_BLOCKED_WORD_RE = re.compile(r"\bblocked\b", re.IGNORECASE)


def _blocked_fact(key_info: str) -> bool:
    """Heuristic: `key_info` names blocked as a whole word (`unblocked` does not match)."""
    return bool(_BLOCKED_WORD_RE.search(key_info or ""))


def _plan_merely_approved(key_info: str) -> bool:
    """`cairn:shared` overwrites `key_info` with `approved` plus the next
    step on approval, so a leading `approved` reads as not yet started."""
    return (key_info or "").strip().lower().startswith("approved")


_DONE_WORD_RE = re.compile(r"\b(done|close|closed|complete)\b", re.IGNORECASE)

_BRANCHING_HEADING_RE = re.compile(r"^##\s+Branching\s*$", re.MULTILINE)
_NEXT_HEADING_RE = re.compile(r"^##\s+", re.MULTILINE)


def _is_direct_commit_project(workflow_path: Path) -> bool:
    """True when `workflow_path`'s `## Branching` section says commits go
    straight to main or that there are no feature branches
    (`/cairn-triage` step 2's own check) - `False` if the file is missing,
    unreadable, or has no `## Branching` section at all."""
    try:
        text = workflow_path.read_text()
    except OSError:
        return False
    heading = _BRANCHING_HEADING_RE.search(text)
    if not heading:
        return False
    rest = text[heading.end() :]
    next_heading = _NEXT_HEADING_RE.search(rest)
    section = rest[: next_heading.start()] if next_heading else rest
    section_lower = section.lower()
    return "direct commit" in section_lower or "no feature branch" in section_lower


def _gh_pr_merged(folder_name: str, project_root: Path, cache: dict, ttl: float) -> bool | None:
    """Whether a PR named after `folder_name` (the task folder's own leaf
    name, used as its branch name by convention) shows as merged, per
    `/cairn-triage` step 3's own `gh pr list` check - cached per
    `(project_root, folder_name)` for `ttl` seconds (§14 Risk sizes this).
    `None` (go by `key_info` instead) for anything but a clean `0`/`1`
    result: non-zero exit, unparseable output, or `gh` missing/unauthenticated
    entirely (§11 - never lets a `gh` problem error the whole board)."""
    key = (str(project_root), folder_name)
    now = time.monotonic()
    cached = cache.get(key)
    if cached is not None and now - cached[0] < ttl:
        return cached[1]

    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--head", folder_name, "--state", "merged", "--json", "number", "-q", "length"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        cache[key] = (now, None)
        return None

    if result.returncode != 0:
        cache[key] = (now, None)
        return None
    output = result.stdout.strip()
    value = {"0": False, "1": True}.get(output)
    cache[key] = (now, value)
    return value


def _done_fact(kind: str, key_info: str, folder_name: str, project_root: Path, gh_cache: dict, gh_ttl: float) -> bool:
    """A merged PR, or `key_info` (or a `review` folder's trailing-line
    equivalent) saying `done`/`close(d)`/`complete` as a whole word - §6.2
    point 2. A `research`-kind folder never checks `gh` (`cairn:shared`);
    neither does a direct-commit project (`/cairn-triage` step 2) - both
    fall back to the `key_info` check alone."""
    key_info_says_done = bool(_DONE_WORD_RE.search(key_info or ""))
    if kind == "research":
        return key_info_says_done
    if _is_direct_commit_project(project_root / ".harness" / "workflow.md"):
        return key_info_says_done
    merged = _gh_pr_merged(folder_name, project_root, gh_cache, gh_ttl)
    return bool(merged) or key_info_says_done


def _column(*, kind: str, key_info: str, has_plan: bool, done: bool, active: bool) -> str:
    """First-match-wins lifecycle stage from a folder's own facts: done ->
    blocked -> awaiting_approval -> in_review (review kind) -> scoping
    (research kind, or no PLAN.md) -> in_review -> building (active, or a plan not merely approved) -> planned.
    A folder with sub-tasks has this overridden afterwards by
    `_apply_parent_rollup` (`parent_tasks` until every child is done)."""
    if done:
        return "done"
    if _blocked_fact(key_info):
        return "blocked"
    if _awaiting_approval_fact(key_info):
        return "awaiting_approval"
    if kind == "review":
        return "in_review"
    if kind == "research" or not has_plan:
        return "scoping"
    if _in_review_fact(key_info):
        return "in_review"
    if active or not _plan_merely_approved(key_info):
        return "building"
    return "planned"


# --------------------------------------------------------------------------
# §8: the `active` subagent-marker read (read-only)
# --------------------------------------------------------------------------


def _apply_parent_rollup(cards: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """The one exception to `_column`'s first-match precedence: a card with
    sub-task children takes its column from them alone - `done` (and
    `done: True`) once every direct child's column is `done`, else
    `parent_tasks` (and `done: False`) - whatever its own merged PR,
    `key_info` done word, blocked or approval facts say. Cards are visited
    deepest first so a nested parent's rolled-up column is final before its
    own parent reads it. `needs_attention` and `active` are left alone.
    Mutates `cards` in place; returns the `(project, parent folder) ->
    direct children` grouping so callers don't rebuild it."""
    children_by_parent: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for card in cards:
        if card["parent"] is not None:
            children_by_parent[(card["project"], card["parent"])].append(card)

    for card in sorted(cards, key=lambda c: c["folder"].count("/"), reverse=True):
        children = children_by_parent.get((card["project"], card["folder"]))
        if children:
            all_done = all(c["column"] == "done" for c in children)
            card["column"] = "done" if all_done else "parent_tasks"
            card["done"] = all_done
    return children_by_parent


def _active_heartbeats(heartbeat_dir: Path, now: float) -> set[tuple[str, str]]:
    """`(project, task)` pairs (as written by a marker file's own JSON, §8)
    with at least one `*.active` subagent marker under `heartbeat_dir` no
    older than `MARKER_MAX_AGE_SECONDS`. The session pointer
    (`<session_id>.json`) is not read: only a running subagent's marker
    counts. A missing directory, or an expired/corrupt/non-dict/wrong-shaped
    file, just contributes nothing - read-only and never raises."""
    live: set[tuple[str, str]] = set()
    if not heartbeat_dir.is_dir():
        return live
    for path in heartbeat_dir.glob("*.active"):
        try:
            if now - path.stat().st_mtime > MARKER_MAX_AGE_SECONDS:
                continue
            payload = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        project, task = payload.get("project"), payload.get("task")
        if isinstance(project, str) and isinstance(task, str):
            live.add((project, task))
    return live


# --------------------------------------------------------------------------
# Card assembly (§6.1-6.4, §9)
# --------------------------------------------------------------------------


def _card_fields(
    folder_dir: Path,
    source_path: Path,
    project,
    tasks_root: Path,
    live_heartbeats: set[tuple[str, str]],
    gh_cache: dict,
    gh_ttl: float,
) -> dict | None:
    """One folder's `GET /api/tasks` card fields (everything but `sub_tasks`,
    which `build_cards`/`build_detail` each compute their own way) - shared
    by both, so a card's own facts (column precedence, `active`) are
    computed identically whether it's rendered in the board's flat list or
    as a parent's own sub-task-list entry in the detail drawer (§9).
    `None` if `source_path` can't be read (degrade, not crash)."""
    try:
        text = source_path.read_text()
    except OSError:
        return None

    relative_folder = folder_dir.relative_to(project.root).as_posix()
    kind = _folder_kind(folder_dir.name)
    parent = _parent_relpath(folder_dir, project.root)

    if source_path.name == "DRAFT.md":
        goal, key_info = _draft_summary(text)
        last_log_date = _folder_name_date(folder_dir, tasks_root)
        last_log_time = ""
    else:
        frontmatter = parse_frontmatter(text)
        goal = frontmatter.get("goal", "")
        key_info = frontmatter.get("key_info", "")
        goal = goal if isinstance(goal, str) else ""
        key_info = key_info if isinstance(key_info, str) else ""
        last_log_datetime = _last_log_datetime(text)
        last_log_date = (last_log_datetime[0] if last_log_datetime else None) or _folder_name_date(
            folder_dir, tasks_root
        )
        last_log_time = last_log_datetime[1] if last_log_datetime else ""

    needs_attention = _needs_attention_fact(key_info)
    done = _done_fact(kind, key_info, folder_dir.name, project.root, gh_cache, gh_ttl)
    active = (str(project.root), relative_folder) in live_heartbeats
    has_plan = (folder_dir / "PLAN.md").is_file()

    return {
        "project": project.label,
        "folder": relative_folder,
        "parent": parent,
        "kind": kind,
        "goal": goal,
        "key_info": key_info,
        "last_log_date": last_log_date,
        "last_log_time": last_log_time,
        "column": _column(kind=kind, key_info=key_info, has_plan=has_plan, done=done, active=active),
        "active": active,
        "needs_attention": needs_attention,
        "done": done,
        "_sort_key": _last_touched_sort_key(last_log_date, last_log_time),
    }


def build_cards(
    projects: list,
    *,
    heartbeat_dir: Path | None = None,
    now: float | None = None,
    gh_cache: dict | None = None,
    gh_ttl: float = GH_CACHE_TTL_SECONDS,
) -> list[dict]:
    """One card per `docs/tasks/**/STATE.md`/`DRAFT.md` folder across every
    `project` in `projects` (each a `.label`/`.root`-bearing object, e.g.
    `server.Project`), shaped per `PRD.md` §9's `GET /api/tasks` schema.
    `heartbeat_dir` (default `DEFAULT_HEARTBEAT_DIR`) and `now` (default
    wall-clock) parameterize the `active` read for testability; `gh_cache`
    should be a dict the caller holds across requests so the `gh pr list`
    TTL cache (§14) actually persists between calls."""
    heartbeat_dir = heartbeat_dir if heartbeat_dir is not None else DEFAULT_HEARTBEAT_DIR
    gh_cache = gh_cache if gh_cache is not None else {}
    request_time = now if now is not None else time.time()
    live_heartbeats = _active_heartbeats(heartbeat_dir, request_time)

    cards: list[dict] = []
    for project in projects:
        tasks_root = project.root / "docs" / "tasks"
        for folder_dir, source_path in _iter_task_dirs(project.root):
            card = _card_fields(folder_dir, source_path, project, tasks_root, live_heartbeats, gh_cache, gh_ttl)
            if card is not None:
                cards.append(card)

    # §6.4: direct-child count per parent, one level, done = children whose
    # rolled-up column is Done - scoped by project so two projects' folders
    # that happen to share a relative path never mix.
    children_by_parent = _apply_parent_rollup(cards)

    for card in cards:
        children = children_by_parent.get((card["project"], card["folder"]))
        if children:
            card["sub_tasks"] = {"done": sum(1 for c in children if c["column"] == "done"), "total": len(children)}
        else:
            card["sub_tasks"] = None

    # Most-recently-touched first, using the finer date+time precision
    # `_last_touched_sort_key` computed per card - `_sort_key` is transient
    # (leading underscore, matching this module's own private-helper
    # naming) and never part of the `GET /api/tasks` response shape.
    cards.sort(key=lambda c: c["_sort_key"], reverse=True)
    for card in cards:
        del card["_sort_key"]

    return cards


# --------------------------------------------------------------------------
# Detail drawer assembly (§6.5, §6.6, §9's `GET /api/tasks/detail`)
# --------------------------------------------------------------------------


def _list_docs(folder_dir: Path) -> list[dict]:
    """Every `*.md` file directly under `folder_dir` except whichever of
    `STATE.md`/`DRAFT.md` the Details tab already shows (`DRAFT.md` only
    when there is no `STATE.md`, as in an older `review` folder), as name/byte-size/
    mtime metadata only - never content (§6.6). Not recursive: a subfolder
    of loose assets (`wireframes/`, `mockups/`) is never a "doc" and isn't
    listed. `docs/tasks/` is gitignored per-project, so filesystem mtime -
    not a git log - is the honest "last touched" signal here."""
    docs: list[dict] = []
    shown = {"STATE.md"} if (folder_dir / "STATE.md").is_file() else {"DRAFT.md"}
    for path in sorted(folder_dir.glob("*.md")):
        if path.name in shown or not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        docs.append(
            {
                "name": path.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
            }
        )
    return docs


def build_detail(
    project,
    folder_dir: Path,
    *,
    heartbeat_dir: Path | None = None,
    now: float | None = None,
    gh_cache: dict | None = None,
    gh_ttl: float = GH_CACHE_TTL_SECONDS,
) -> dict | None:
    """One folder's detail-drawer payload, shaped per `PRD.md` §9's second
    JSON block (`GET /api/tasks/detail`): frontmatter plus the parsed
    activity timeline, XOR (for a `DRAFT.md`-only `review` folder)
    `draft_content` in its place (§6.5) - the full direct-child sub-task
    list (folder/column/goal, unlike `build_cards`'s summary-only
    `{done, total}`), and `docs` metadata (§6.6). `None` when `folder_dir`
    holds neither a `STATE.md` nor a `DRAFT.md` - the caller's 404."""
    state_path = folder_dir / "STATE.md"
    draft_path = folder_dir / "DRAFT.md"
    source_path = state_path if state_path.is_file() else draft_path if draft_path.is_file() else None
    if source_path is None:
        return None

    heartbeat_dir = heartbeat_dir if heartbeat_dir is not None else DEFAULT_HEARTBEAT_DIR
    gh_cache = gh_cache if gh_cache is not None else {}
    request_time = now if now is not None else time.time()
    live_heartbeats = _active_heartbeats(heartbeat_dir, request_time)
    tasks_root = project.root / "docs" / "tasks"

    card = _card_fields(folder_dir, source_path, project, tasks_root, live_heartbeats, gh_cache, gh_ttl)
    if card is None:
        return None

    # The folder plus every descendant, rolled up the same way `build_cards`
    # does, so the drawer's column (and each child entry's) matches the board.
    subtree = [card]
    for child_dir, child_source in _iter_task_dirs(project.root):
        if child_dir != folder_dir and child_dir.is_relative_to(folder_dir):
            child_card = _card_fields(child_dir, child_source, project, tasks_root, live_heartbeats, gh_cache, gh_ttl)
            if child_card is not None:
                subtree.append(child_card)
    children_by_parent = _apply_parent_rollup(subtree)

    if source_path.name == "DRAFT.md":
        frontmatter = {"goal": card["goal"], "key_info": card["key_info"]}
        activity = None
        draft_content = source_path.read_text()
    else:
        text = source_path.read_text()
        frontmatter = parse_frontmatter(text)
        activity = parse_activity(text)
        draft_content = None

    children = children_by_parent.get((card["project"], card["folder"]))
    sub_tasks = None
    if children:
        sub_tasks = [
            {
                "folder": child_card["folder"],
                "column": child_card["column"],
                "needs_attention": child_card["needs_attention"],
                "active": child_card["active"],
                "goal": child_card["goal"],
            }
            for child_card in children
        ]

    return {
        "project": card["project"],
        "folder": card["folder"],
        "parent": card["parent"],
        "kind": card["kind"],
        "column": card["column"],
        "needs_attention": card["needs_attention"],
        "active": card["active"],
        "frontmatter": frontmatter,
        "activity": activity,
        "draft_content": draft_content,
        "sub_tasks": sub_tasks,
        "docs": _list_docs(folder_dir),
    }
