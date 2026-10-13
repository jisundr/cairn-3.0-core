#!/usr/bin/env python3
"""Write <root>/.cairn/export/tasks.json, schema 1 (docs/schemas/tasks-v1.md).

    python tasks-export.py --root DIR [--session ID]

Reads docs/tasks/**/STATE.md|DRAFT.md and the private ledger
.cairn/task-sessions.jsonl; with --session it first samples that session's
task pointer into the ledger. Stdlib only, with its own small frontmatter
parser (same precedent as proposals.py). Phase comes from files alone: no
gh call and no marker read. Exit 0 always; any failure leaves the previous
file in place.
"""
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1
LEDGER = "task-sessions.jsonl"
COMPACT_ABOVE = 500  # ledger lines
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SESSION_RE = re.compile(r"^[A-Za-z0-9_-]+$")
DEFAULT_ARCHIVE = "docs/tasks/.archived/"
KEY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*):(.*)$")
KIND_RE = re.compile(r"^(?:\d{4}-\d{2}-\d{2}-\d{4}|\d{2})-(build|research|review)-")
LOG_RE = re.compile(
    r"^- (\d{4}-\d{2}-\d{2})(?: (\d{2}:\d{2}))?|^(\d{4}-\d{2}-\d{2})(?:/\d{2})?(?: (\d{2}:\d{2}))?:",
    re.M,
)
DONE_RE = re.compile(r"\b(done|close|closed|complete)\b", re.I)
BLOCKED_RE = re.compile(r"\bblocked\b", re.I)
REVIEW_RE = re.compile(r"\b(review|reviewer)\b", re.I)
APPROVAL = ("awaiting requirements approval", "awaiting plan approval")
ATTENTION = ("needs-human", "stalled")


def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- frontmatter (scalars only are needed: goal, key_info) ----

def _unquote(v):
    v = v.strip()
    return v[1:-1] if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'" else v


def frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, None
    for end in range(1, len(lines)):
        if lines[end].strip() == "---":
            break
    else:
        return {}, None
    out = {}
    for line in lines[1:end]:
        m = KEY_RE.match(line)
        if m and m.group(2).strip():
            v = _unquote(m.group(2))
            # list-valued key_info is invalid per state-v1: read as empty
            out[m.group(1)] = "" if m.group(1) == "key_info" and v.startswith("[") else v
    return out, end


def last_log(text, end):
    body = "\n".join(text.splitlines()[end + 1:] if end is not None else text.splitlines())
    found = list(LOG_RE.finditer(body))
    if not found:
        return None
    d1, t1, d2, t2 = found[-1].groups()
    date, time = d1 or d2, t1 or t2
    return f"{date} {time}" if time else date


# ---- discovery ----

def archive_dir(root):
    """Normalized archive path (trailing slash) or None when invalid."""
    path = DEFAULT_ARCHIVE
    try:
        text = (root / ".harness/workflow.md").read_text()
    except OSError:
        text = ""
    m = re.search(r"^##\s+Archive\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if m:
        p = re.search(r"^- Path:\s*(\S+)\s*$", m.group(1), re.M)
        if p:
            path = p.group(1)
    if path.startswith("./"):
        path = path[2:]
    path = re.sub(r"/+", "/", path).rstrip("/") + "/"
    segs = path.strip("/").split("/")
    bad = (
        not re.fullmatch(r"[A-Za-z0-9._/-]+", path)
        or path.startswith("/")
        or ".." in segs
        or not path.startswith("docs/")
        or path == "docs/tasks/"
        or any(s in (".git", ".claude", ".github") for s in segs)
        or (len(segs) == 3 and segs[:2] == ["docs", "tasks"] and (root / path / "STATE.md").is_file())
    )
    return None if bad else path


def is_task_folder(d):
    return (d / "STATE.md").is_file() or (d / "DRAFT.md").is_file()


def folders(root):
    base = root / "docs" / "tasks"
    if not base.is_dir():
        return
    seen = set()
    for p in sorted(base.glob("**/STATE.md")):
        seen.add(p.parent)
        yield p.parent, p
    for p in sorted(base.glob("**/DRAFT.md")):
        if p.parent not in seen:
            yield p.parent, p


def draft_summary(text):
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    return (lines[0].lstrip("#").strip(), lines[-1]) if lines else ("", "")


def phase_of(kind, key_info, has_plan):
    """First match, from files only; mirrors mission-control/tasks.py _column."""
    if DONE_RE.search(key_info):
        return "done"
    if BLOCKED_RE.search(key_info):
        return "blocked"
    if any(s in key_info for s in APPROVAL):
        return "awaiting_approval"
    if kind == "review":
        return "in_review"
    if kind == "research" or not has_plan:
        return "scoping"
    if REVIEW_RE.search(key_info):
        return "in_review"
    if not key_info.strip().lower().startswith("approved"):
        return "building"
    return "planned"


def read_tasks(root):
    skip = archive_dir(root)
    tasks = []
    for d, src in folders(root):
        rel = d.relative_to(root).as_posix()
        if "_template" in d.relative_to(root).parts:
            continue
        if skip and (rel + "/").startswith(skip):
            continue
        try:
            text = src.read_text()
        except OSError:
            continue
        kind = (KIND_RE.match(d.name) or [None, "build"])[1]
        if src.name == "DRAFT.md":
            goal, key_info = draft_summary(text)
            log = None
        else:
            fm, end = frontmatter(text)
            goal, key_info = fm.get("goal", ""), fm.get("key_info", "")
            log = last_log(text, end)
        parent = d.parent
        parent_rel = None
        if parent != root and parent.is_relative_to(root) and is_task_folder(parent):
            parent_rel = parent.relative_to(root).as_posix()
        tasks.append({
            "folder": rel, "parent": parent_rel, "kind": kind, "goal": goal,
            "key_info": key_info,
            "phase": phase_of(kind, key_info, (d / "PLAN.md").is_file()),
            "needs_attention": any(s in key_info for s in ATTENTION),
            "last_log": log, "sessions": [],
        })
    # A folder with sub-tasks: parent_tasks until every child is done.
    kids = {}
    for t in tasks:
        if t["parent"]:
            kids.setdefault(t["parent"], []).append(t)
    for t in sorted(tasks, key=lambda t: t["folder"].count("/"), reverse=True):
        if t["folder"] in kids:
            t["phase"] = "done" if all(c["phase"] == "done" for c in kids[t["folder"]]) else "parent_tasks"
    return tasks


# ---- ledger ----

def _valid(rec):
    return (
        isinstance(rec, dict)
        and all(isinstance(rec.get(k), str) and rec[k] for k in ("session", "project", "task"))
        and all(isinstance(rec.get(k), str) and TS_RE.match(rec[k]) for k in ("start", "end"))
    )


def read_ledger(path):
    """Raw valid records, in file order; unreadable lines are skipped."""
    recs = []
    try:
        for line in path.read_text().splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if _valid(rec):
                recs.append(rec)
    except OSError:
        pass
    return recs


def merge(recs):
    """One entry per (session, task): min start, max end."""
    out = {}
    for r in recs:
        key = (r["session"], r["task"])
        cur = out.get(key)
        if cur is None:
            out[key] = dict(r)
        else:
            cur["start"] = min(cur["start"], r["start"])
            cur["end"] = max(cur["end"], r["end"])
    return list(out.values())


def sample_pointer(root, session, now):
    """Append the session's task pointer to the ledger as one line."""
    if not SESSION_RE.match(session or ""):
        return
    try:
        ptr = json.loads((Path.home() / ".claude/cairn/active" / f"{session}.json").read_text())
        task, project = ptr["task"], ptr["project"]
        if not (isinstance(task, str) and task and isinstance(project, str)):
            return
        if Path(project).resolve() != root.resolve():
            return
    except (OSError, ValueError, KeyError, TypeError):
        return
    start = now
    try:
        for line in (root / ".cairn/sessions.log").read_text().splitlines():
            ts, _, rest = line.partition("\t")
            if rest.rsplit("\t", 1)[-1] == session and TS_RE.match(ts):
                start = min(start, ts)
    except OSError:
        pass
    rec = {"session": session, "project": str(root), "task": task, "start": start, "end": now}
    with open(root / ".cairn" / LEDGER, "a") as f:
        f.write(json.dumps(rec, separators=(",", ":")) + "\n")


def compact(path):
    try:
        size = path.stat().st_size
        n = len(path.read_text().splitlines())
    except OSError:
        return
    if n > COMPACT_ABOVE:
        body = "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in merge(read_ledger(path)))
        try:  # a concurrent append changed the file: skip, the next Stop retries
            if path.stat().st_size != size:
                return
        except OSError:
            return
        atomic_write(path, body)


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---- export ----

def build(root, now=None):
    root = Path(root)
    tasks = read_tasks(root)
    by_task = {t["folder"]: t for t in tasks}
    for r in merge(read_ledger(root / ".cairn" / LEDGER)):
        t = by_task.get(r["task"])
        if t is not None and Path(r["project"]).resolve() == root:
            t["sessions"].append({"session_id": r["session"], "started": r["start"], "ended": r["end"]})
    for t in tasks:
        t["sessions"].sort(key=lambda s: (s["started"], s["session_id"]))
    return {"schema": SCHEMA, "generated": now or now_utc(), "project": str(root), "tasks": tasks}


def export(root, session=None, now=None):
    root = Path(root).resolve()
    if not (root / ".cairn").is_dir():
        return None
    now = now or now_utc()
    if session:
        sample_pointer(root, session, now)
    compact(root / ".cairn" / LEDGER)
    doc = build(root, now)
    out = root / ".cairn" / "export" / "tasks.json"
    try:  # unchanged content (apart from `generated`) keeps the file as is
        old = json.loads(out.read_text())
        if {**old, "generated": ""} == {**doc, "generated": ""}:
            return out
    except (OSError, ValueError):
        pass
    atomic_write(out, json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    return out


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", required=True)
    ap.add_argument("--session", default="")
    args = ap.parse_args(argv)
    try:
        export(args.root, args.session)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
