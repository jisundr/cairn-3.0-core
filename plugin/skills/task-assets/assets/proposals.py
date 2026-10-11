#!/usr/bin/env python3
"""Queue of harness-rule proposals; the contract is in proposals.md.

    proposals.py record --root R --session S --transcript P
    proposals.py count  --root R
    proposals.py list   --root R [--limit N] [--json]
    proposals.py apply  --root R ID --file F --section "## X" --line "- ..."
    proposals.py mark   --root R ID dropped [--note T]

record and count exit 0 on every path (a hook runs them). Mechanical only: no
model call, no network. Stdlib, Python 3.11.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

N_SESSION = 5
N_BATCH = 5
QUEUE_MAX = 25
EXPIRE_DAYS = 30
KEEP_DAYS = 90
SIGNAL_MAX = 300
CONTEXT_MAX = 200
NOTE_MAX = 120
SCAN_MAX = 2_000_000
SEEN_MAX = 10
JACCARD = 0.7
HARNESS_CAPS = {"architecture.md": 40, "standards.md": 40, "environment.md": 30, "workflow.md": 30}
BLOCKED_SECTIONS = ("gates", "release")
FIELDS = ("schema", "id", "type", "signal", "context", "status", "session", "time",
          "last_seen", "count", "seen", "resolved", "applied_to", "note")
CUE_RE = re.compile(
    r"\bno\b|\bdon'?t\b|\bdo not\b|\bstop\b|\binstead\b|\bwrong\b|\bthat'?s not\b|\bnot that\b"
    r"|\bshould be\b|\bi said\b|\bi told you\b|\bi meant\b|\bactually\b", re.I)
SECRET_RE = re.compile(
    r"key|secret|token|passw|credential|sk-[\w-]{16,}|\bgh[pousr]_\w+|AKIA\w{12,}|\b[A-Za-z0-9_-]{32,}\b",
    re.I)
TS_FMT = "%Y-%m-%dT%H:%M:%SZ"


def now():
    return datetime.now(timezone.utc)


def stamp(dt):
    return dt.strftime(TS_FMT)


def parse_ts(text):
    try:
        return datetime.strptime(text[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def clean_ts(text):
    dt = parse_ts(text) if isinstance(text, str) else None
    return stamp(dt) if dt else stamp(now())


def collapse(text, limit):
    return " ".join(str(text).split())[:limit]


def signal_id(text):
    norm = " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]


def qdir(root):
    return Path(root) / ".cairn" / "proposals"


def load(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("id") else None


def save(directory, entry):
    """Atomic write, keys in contract order; mtime is last_seen or resolved."""
    directory.mkdir(parents=True, exist_ok=True)
    ordered = {k: entry.get(k) for k in FIELDS}
    target = directory / (entry["id"] + ".json")
    tmp = directory / (".tmp.%s.%d" % (entry["id"], os.getpid()))
    tmp.write_text(json.dumps(ordered, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    when = parse_ts(entry.get("resolved") or entry.get("last_seen") or "")
    if when:
        os.utime(target, (when.timestamp(), when.timestamp()))


def entries(directory):
    out = []
    if directory.is_dir():
        for p in sorted(directory.glob("*.json")):
            e = load(p)
            if e:
                out.append(e)
    return out


def sweep(directory, at=None):
    """Delete queued entries past EXPIRE_DAYS and resolved ones past KEEP_DAYS."""
    at = at or now()
    for e in entries(directory):
        if e.get("status") == "queued":
            ref, days = parse_ts(e.get("last_seen")), EXPIRE_DAYS
        else:
            ref, days = parse_ts(e.get("resolved") or e.get("last_seen")), KEEP_DAYS
        if ref and at - ref > timedelta(days=days):
            try:
                (directory / (e["id"] + ".json")).unlink()
            except OSError:
                pass


def queued(directory, at=None):
    at = at or now()
    out = []
    for e in entries(directory):
        ts = parse_ts(e.get("last_seen"))
        if e.get("status") == "queued" and ts and at - ts <= timedelta(days=EXPIRE_DAYS):
            out.append(e)
    return out


# --- extraction ---------------------------------------------------------

def user_text(entry):
    """The typed text of a human user entry, or None."""
    if entry.get("isMeta") or entry.get("isSidechain"):
        return None
    origin = entry.get("origin")
    kind = origin.get("kind") if isinstance(origin, dict) else None
    if kind not in (None, "human") or entry.get("promptSource") in ("suggestion_accepted", "system"):
        return None
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, list):
        if any(not isinstance(b, dict) or b.get("type") != "text" for b in content):
            return None
        content = "\n".join(b.get("text", "") for b in content)
    return content.strip() if isinstance(content, str) else None


def is_correction(text):
    if not 3 <= len(text) <= 600 or text[0] in "</":
        return False
    return bool(CUE_RE.search(text[:80].replace("’", "'")))


def result_text(block):
    content = block.get("content")
    if isinstance(content, list):
        content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return content if isinstance(content, str) else ""


def extract(lines, session_time):
    """Yield signal dicts from transcript lines (already decoded)."""
    bash = {}
    failed = None
    for raw in lines:
        try:
            e = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(e, dict):
            continue
        kind = e.get("type")
        if kind == "user":
            text = user_text(e)
            if text and is_correction(text) and not SECRET_RE.search(text):
                yield {"type": "correction", "signal": collapse(text, SIGNAL_MAX), "context": "",
                       "time": clean_ts(e.get("timestamp") or session_time)}
        content = (e.get("message") or {}).get("content")
        if not isinstance(content, list) or e.get("isSidechain"):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if kind == "assistant" and b.get("type") == "tool_use" and b.get("name") == "Bash":
                cmd = (b.get("input") or {}).get("command")
                if isinstance(cmd, str):
                    bash[b.get("id")] = collapse(cmd, SIGNAL_MAX)
            elif kind == "user" and b.get("type") == "tool_result" and b.get("tool_use_id") in bash:
                cmd, body = bash[b["tool_use_id"]], result_text(b)
                if b.get("is_error") is True and body.startswith("Exit code"):
                    lines_ = [x for x in body.splitlines()[1:] if x.strip()]
                    failed = (cmd, lines_[0] if lines_ else body.splitlines()[0],
                              clean_ts(e.get("timestamp") or session_time))
                else:
                    if failed and cmd != failed[0] and not b.get("is_error"):
                        ctx = collapse("%s | worked: %s" % (collapse(failed[1], 100), cmd), CONTEXT_MAX)
                        if not SECRET_RE.search(failed[0] + ctx):
                            yield {"type": "failure", "signal": failed[0], "context": ctx, "time": failed[2]}
                    failed = None


def read_pos(directory, session):
    try:
        off, rec = (directory / (".pos-" + session)).read_text().split()
        return int(off), int(rec)
    except (OSError, ValueError):
        return 0, 0


def record(root, session, transcript):
    directory = qdir(root)
    directory.mkdir(parents=True, exist_ok=True)
    sweep(directory)
    offset, recorded = read_pos(directory, session)
    size = os.path.getsize(transcript)
    if size < offset:
        offset = 0
    with open(transcript, "rb") as fh:
        fh.seek(offset)
        chunk = fh.read(SCAN_MAX)
    end = chunk.rfind(b"\n") + 1
    if end == 0 and len(chunk) < SCAN_MAX and offset + len(chunk) >= size:
        end = len(chunk)
    text = chunk[:end].decode("utf-8", errors="replace")
    signals = list(extract(text.splitlines(), stamp(now())))
    signals.sort(key=lambda s: s["type"] != "correction")
    open_count = len(queued(directory))
    for s in signals:
        sid = signal_id(s["signal"])
        path = directory / (sid + ".json")
        existing = load(path)
        if existing:
            if existing.get("status") != "queued" or [session, s["time"]] in existing.get("seen", []):
                continue
            existing["count"] = int(existing.get("count", 1)) + 1
            existing["last_seen"] = max(existing.get("last_seen", ""), s["time"])
            existing["seen"] = (existing.get("seen", []) + [[session, s["time"]]])[-SEEN_MAX:]
            save(directory, existing)
        elif recorded < N_SESSION and open_count < QUEUE_MAX:
            save(directory, {"schema": 1, "id": sid, "type": s["type"], "signal": s["signal"],
                             "context": s["context"], "status": "queued", "session": session,
                             "time": s["time"], "last_seen": s["time"], "count": 1,
                             "seen": [[session, s["time"]]], "resolved": None,
                             "applied_to": None, "note": ""})
            recorded += 1
            open_count += 1
    (directory / (".pos-" + session)).write_text("%d %d\n" % (offset + end, recorded))


# --- review: list, apply, mark -------------------------------------------

def words(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 3}


def similar(a, b):
    wa, wb = words(a), words(b)
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= JACCARD


def rule_texts(root):
    out = []
    for name in HARNESS_CAPS:
        path = Path(root) / ".harness" / name
        if path.is_file():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("- "):
                    body = line[2:].split(" | evidence: ")[0].split(" | applies when: ")[0]
                    out.append((name, body))
    return out


def cmd_list(root, limit, as_json):
    directory = qdir(root)
    sweep(directory)
    items = sorted(queued(directory), key=lambda e: (e["count"], e["last_seen"]), reverse=True)
    rules = rule_texts(root)
    shown = items[:limit]
    for e in shown:
        hit = next((n + ": " + t for n, t in rules if similar(e["signal"], t)), None)
        if hit is None:
            other = next((o for o in items if o["id"] != e["id"] and similar(e["signal"], o["signal"])), None)
            hit = "queued " + other["id"] if other else None
        e["dup"] = hit
    if as_json:
        print(json.dumps({"items": shown, "more": len(items) - len(shown)}, ensure_ascii=False))
        return 0
    for i, e in enumerate(shown, 1):
        print("%d. %s %s x%d last %s: %s" % (i, e["id"], e["type"], e["count"], e["last_seen"][:10], e["signal"]))
        if e["context"]:
            print("   context: " + e["context"])
        if e["dup"]:
            print("   possible duplicate of " + e["dup"])
    if len(items) > len(shown):
        print("+%d more queued" % (len(items) - len(shown)))
    if not items:
        print("no proposals queued")
    return 0


def rules_checker():
    path = Path(__file__).with_name("rules-check.py")
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("rules_check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def refuse(reason):
    print("refused: " + reason)
    return 1


def cmd_apply(root, pid, fname, section, line):
    directory = qdir(root)
    entry = load(directory / (pid + ".json"))
    if not entry:
        return refuse("unknown id " + pid)
    if entry.get("status") != "queued":
        return refuse("id %s is %s" % (pid, entry.get("status")))
    name = fname.rsplit("/", 1)[-1]
    if name not in HARNESS_CAPS or fname not in (name, ".harness/" + name):
        return refuse("file must be one of " + ", ".join(HARNESS_CAPS))
    if not line.startswith("- ") or len(line) < 4 or "\n" in line or "\r" in line:
        return refuse("line must be one physical bullet starting with '- '")
    heading = section.strip()
    if not heading.startswith("##") or heading.lstrip("#").strip().lower().split(" ")[0] in BLOCKED_SECTIONS:
        return refuse("section must be a ## heading other than Gates or Release")
    checker = rules_checker()
    if checker is not None:
        parsed = checker.parse_rule_line(line + "\n")
        state, why = checker.check_rule(parsed, root) if parsed else ("malformed", "not a rule bullet")
        if state == "malformed":
            return refuse("line is malformed: " + why)
    path = Path(root) / ".harness" / name
    if not path.is_file():
        return refuse("missing " + str(path))
    old = path.read_text(encoding="utf-8").splitlines()
    if line in old:
        return refuse("line already present")
    if len(old) + 1 > HARNESS_CAPS[name]:
        return refuse("%s is at its %d-line cap" % (name, HARNESS_CAPS[name]))
    at = None
    fenced = False
    for i, raw in enumerate(old):
        if raw.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and raw.rstrip() == heading:
            at = i
            break
    if at is None:
        return refuse("section not found: " + heading)
    last, fenced, j = None, False, at + 1
    while j < len(old):
        raw = old[j]
        if raw.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and raw.startswith("#"):
            break
        if not fenced and raw.startswith("- "):
            last = j
        j += 1
    if last is not None:
        pos = last + 1
        while pos < len(old) and old[pos][:1] in (" ", "\t") and old[pos].strip():
            pos += 1
    else:
        pos = at + 1 + (1 if at + 1 < len(old) and not old[at + 1].strip() else 0)
    new = old[:pos] + [line] + old[pos:]
    tmp = path.with_name(".tmp." + name)
    tmp.write_text("\n".join(new) + "\n", encoding="utf-8")
    back = tmp.read_text(encoding="utf-8").splitlines()
    if len(back) != len(old) + 1 or back[:pos] + back[pos + 1:] != old or back[pos] != line:
        tmp.unlink()
        return refuse("write verification failed")
    os.replace(tmp, path)
    entry.update(status="approved", resolved=stamp(now()), applied_to="%s:%d" % (name, pos + 1))
    save(directory, entry)
    print("applied to %s:%d" % (name, pos + 1))
    return 0


def cmd_mark(root, pid, note):
    directory = qdir(root)
    entry = load(directory / (pid + ".json"))
    if not entry:
        return refuse("unknown id " + pid)
    if entry.get("status") != "queued":
        return refuse("id %s is %s" % (pid, entry.get("status")))
    entry.update(status="dropped", resolved=stamp(now()), note=collapse(note or "", NOTE_MAX))
    save(directory, entry)
    print("dropped " + pid)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("record", "count", "list", "apply", "mark"):
        p = sub.add_parser(name)
        p.add_argument("--root", default=".")
        if name == "record":
            p.add_argument("--session", required=True)
            p.add_argument("--transcript", required=True)
        if name == "list":
            p.add_argument("--limit", type=int, default=N_BATCH)
            p.add_argument("--json", action="store_true")
        if name in ("apply", "mark"):
            p.add_argument("id")
        if name == "apply":
            p.add_argument("--file", required=True)
            p.add_argument("--section", required=True)
            p.add_argument("--line", required=True)
        if name == "mark":
            p.add_argument("status", choices=["dropped"])
            p.add_argument("--note", default="")
    if argv is None:
        argv = sys.argv[1:]
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        # hooks must never fail on bad usage; review commands report it
        return 0 if argv[:1] in (["record"], ["count"]) else (exc.code or 2)
    try:
        if args.cmd == "record":
            record(args.root, args.session, args.transcript)
        elif args.cmd == "count":
            print(len(queued(qdir(args.root))))
        elif args.cmd == "list":
            return cmd_list(args.root, args.limit, args.json)
        elif args.cmd == "apply":
            return cmd_apply(args.root, args.id, args.file, args.section, args.line)
        else:
            return cmd_mark(args.root, args.id, args.note)
    except Exception as exc:  # record and count never block a hook
        if args.cmd in ("record", "count"):
            return 0
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
