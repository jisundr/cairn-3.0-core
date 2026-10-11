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
import contextlib
import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # no flock: fall back to an O_EXCL lock file
    fcntl = None

N_SESSION = 5
N_BATCH = 5
QUEUE_MAX = 25
EXPIRE_DAYS = 30
KEEP_DAYS = 90
SIGNAL_MAX = 300
CONTEXT_MAX = 200
NOTE_MAX = 120
FAIL_MAX = 2
LOCK_WAIT = 10.0
RECORD_WAIT = 3.0  # the Stop hook times out at 5 s
TMP_MAX_AGE = 3600
LOCK_STALE = 30.0
SCAN_MAX = 2_000_000
BLOCK = 1 << 20
SEEN_MAX = 10
JACCARD = 0.7
HARNESS_CAPS = {"architecture.md": 40, "standards.md": 40, "environment.md": 30, "workflow.md": 30}
BLOCKED_SECTIONS = ("gates", "release")
FIELDS = ("schema", "id", "type", "signal", "context", "status", "session", "time",
          "last_seen", "count", "seen", "resolved", "applied_to", "note")
CUE_RE = re.compile(
    r"\bno\b|\bdon'?t\b|\bdo not\b|\bstop\b|\binstead\b|\bwrong\b|\bthat'?s not\b|\bnot that\b"
    r"|\bshould be\b|\bi said\b|\bi told you\b|\bi meant\b|\bactually\b", re.I)
SECRET_CI = [
    r"://[^/\s]*@", r"bearer", r"authorization", r"\bbasic\s+[A-Za-z0-9+/=]{8,}", r"\bpwd\b",
    r"\bxox[a-z]-", r"\b(?:rk|pk|sk)_", r"hooks\.slack\.com", r"[?&](?:sig|token|key|secret|signature)=",
    r"secret", r"token", r"passw", r"credential", r"api[ _-]?key|secret[ _-]?key", r"private[ _-]?key",
    r"\b(?:access|auth|ssh|signing|encryption)[ _-]?key", r"\bkey\s*[:=]",
    r"sk-[\w-]{16,}", r"\bgh[pousr]_\w+", r"github_pat_", r"BEGIN [A-Z ]*PRIVATE", r"\beyJ[\w-]{5,}\.",
    r"(?<![\w-])-p\S", r"(?<![\w-])(?<!mkdir )-p\s+\S", r"(?<![\w-])-u\s*\S+:\S+",
    r"(?<![\w-])-k\s+\S", r"--user\s+\S+:", r"cookie:", r"set-cookie", r"\bpass(?:wd|word|phrase)?\b\s*[:=]", r"\bpw\b",
    r"passphrase", r"export\s+\w+=", r"glpat-", r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)", r"[A-Za-z0-9_+-]{32,}", r"[A-Za-z0-9+/]{16,}={1,2}",
    r"\b(?=\w*[A-Za-z])(?=\w*\d)\w{6,}[!@#$%^&*]",
]
SECRET_CS = [r"AKIA\w{12,}", r"\bSG\.",
             r"\b(?=[A-Za-z0-9]*[a-z])(?=[A-Za-z0-9]*[A-Z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{10,}\b"]
SECRET_RE = re.compile("|".join(["(?i:%s)" % p for p in SECRET_CI] + SECRET_CS))
# commands whose exit 1 is a normal outcome or whose failure says nothing a rule could use
QUIET_CMDS = {"grep", "egrep", "fgrep", "rg", "diff", "cmp", "test", "[", "find", "which", "command",
              "type", "ls", "cat"}
NOISE_LINE_RE = re.compile(r"^\W*rtk\b", re.I)
ID_RE = re.compile(r"[0-9a-f]{12}\Z")
EVIDENCE_RE = re.compile(r" \| evidence: (?:path|cmd|correction):\S")
TS_FMT = "%Y-%m-%dT%H:%M:%SZ"
WORD_MAX = 20
PATH_MAX = 60
EDGE = ",.;:!?()\"'`\u201c\u201d\u2018\u2019"
WORD_RE = re.compile(r"[^\W\d_]+(?:[-'\u2019+][^\W\d_]+)*\Z")
NUM_RE = re.compile(r"\d{1,6}\Z")
FLAG_RE = re.compile(r"(?:-[A-Za-z]{1,3}|--[A-Za-z]+(?:-[A-Za-z]+)*)\Z")
SEG_RE = re.compile(r"[A-Za-z0-9._~-]+\Z")
SCOPE_RE = re.compile(r"@[A-Za-z][A-Za-z0-9._-]*/[A-Za-z0-9._-]+\Z")
RUN_RE = re.compile(r"[A-Za-z0-9]{12,}")
ENTROPY_RE = re.compile(r"[A-Za-z0-9+_-]{16,}")
NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9._-]*\Z")
WRAPPERS = {"sudo", "time", "nohup", "env", "rtk"}
SUB_RE = re.compile(r"[a-z]+(?:-[a-z]+)*\Z")
SUBCMDS = frozenset(
    "install add remove test run build start stop status push pull commit checkout clone fetch merge rebase"
    " log diff init ci update upgrade publish deploy up down ps exec logs apply plan get list show create"
    " delete config version help lint format check fmt dev serve watch prune worktree stash tag branch"
    " reset restore cleanup migrate seed generate compile bundle pack link unlink doctor".split())
# commands whose first argument is often a secret: the name is stored alone
NAME_ONLY = frozenset("echo printf print login su passwd vault set export kinit htpasswd ssh-add gpg openssl"
                      " security aws gcloud az pass".split())
DIGIT_NAME_RE = re.compile(r"(?:python|pip|pypy|ruby|perl|php|gcc|clang|node|py)\d+(?:\.\d+)*\Z"
                           r"|(?:sha\d+sum|md5sum|base64)\Z")
FAMILIES = [{"npm", "pnpm", "yarn", "bun", "npx", "pnpx"}, {"pip", "pip3", "pipx", "uv"},
            {"python", "python3"}, {"node", "nodejs", "deno", "bun"}, {"docker", "podman"},
            {"make", "gmake"}]


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
    """A transcript timestamp clamped to [now - 365 d, now + 1 d]; now when unreadable."""
    dt = parse_ts(text) if isinstance(text, str) else None
    if dt is None:
        return stamp(now())
    return stamp(min(max(dt, now() - timedelta(days=365)), now() + timedelta(days=1)))


def is_secret(text):
    """True when text looks like it carries a credential; such text is dropped, never redacted."""
    return bool(SECRET_RE.search(text))


def token_ok(tok):
    """True when one whitespace token is a plain word, small number, value-less flag or a short safe path."""
    tok = tok.strip(EDGE)
    if not tok:
        return True
    if not re.search(r"[^\W_]", tok):
        return len(tok) <= 4 and not re.search(r"[=:$@\"'`]", tok)
    for run in ENTROPY_RE.findall(tok):
        low, up, dig = re.search("[a-z]", run), re.search("[A-Z]", run), re.search(r"\d", run)
        if (low and up) or (dig and (low or up)):
            return False
    if WORD_RE.match(tok) and len(tok) <= WORD_MAX:
        return True
    if NUM_RE.match(tok) or FLAG_RE.match(tok):
        return True
    if len(tok) > PATH_MAX:
        return False
    if tok.startswith("@"):
        if not SCOPE_RE.match(tok):
            return False
        tok = tok[1:]
    segs = [x for x in tok.split("/") if x]
    return bool(segs) and all(SEG_RE.match(x) and seg_ok(x) for x in segs)


def seg_ok(seg):
    if RUN_RE.search(seg) or (seg.isdigit() and len(seg) > 6):
        return False
    mixed = re.search("[A-Za-z]", seg) and re.search(r"\d", seg)
    return not (len(seg) >= 10 and mixed and not re.search(r"[._-]", seg))


def text_ok(text):
    """The allow-list for stored text: whole or not at all, never redacted or cut."""
    flat = " ".join(text.split())
    if not flat or len(flat) > SIGNAL_MAX:
        return False
    for t in (text, re.sub(r"[\r\n]+", "", text)):
        if is_secret(t) or not all(token_ok(x) for x in t.split()):
            return False
    return True


def collapse(text, limit):
    return " ".join(str(text).split())[:limit]


def signal_id(text):
    norm = " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]


def pos_path(directory, session):
    """Sanitised id (<= 48) plus 8 hex of sha1 of the raw id, so distinct sessions never share a file."""
    raw = str(session)
    tag = hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()[:8]
    return directory / (".pos-" + re.sub(r"[^\w.-]", "_", raw)[:48] + "-" + tag)


def qdir(root):
    return Path(root) / ".cairn" / "proposals"


def ensure_dir(directory):
    """Create .cairn/ and .cairn/proposals/ and keep both private to the user (0700)."""
    directory.mkdir(parents=True, exist_ok=True)
    for d in (directory.parent, directory):
        with contextlib.suppress(OSError):
            os.chmod(d, 0o700)
    with contextlib.suppress(OSError):  # written by the count hook with the shell's umask
        os.chmod(directory / ".announced", 0o600)


def write_private(path, text):
    """Replace `path` with text, mode 0600, via a unique tmp file."""
    fd, tmp = tempfile.mkstemp(prefix=".tmp.", suffix=".part", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("id") else None


def save(directory, entry):
    """Atomic write, keys in contract order; mtime is last_seen or resolved. Call under locked()."""
    ensure_dir(directory)
    ordered = {k: entry.get(k) for k in FIELDS}
    target = directory / (entry["id"] + ".json")
    write_private(target, json.dumps(ordered, ensure_ascii=False, separators=(",", ":")) + "\n")
    when = parse_ts(entry.get("resolved") or entry.get("last_seen") or "")
    if when:
        os.utime(target, (when.timestamp(), when.timestamp()))


@contextlib.contextmanager
def locked(directory, wait=LOCK_WAIT):
    """Exclusive lock on the queue directory; TimeoutError after `wait` seconds."""
    ensure_dir(directory)
    deadline = time.monotonic() + wait
    if fcntl is not None:
        fd = os.open(str(directory / ".lock"), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise TimeoutError("queue is locked")
                    time.sleep(0.01)
            yield
        finally:
            os.close(fd)  # closing drops the flock
        return
    path = str(directory / ".lock.excl")
    while True:
        try:
            os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
            break
        except FileExistsError:
            try:
                if time.time() - os.stat(path).st_mtime > LOCK_STALE:
                    os.unlink(path)
                    continue
            except OSError:
                continue
            if time.monotonic() > deadline:
                raise TimeoutError("queue is locked")
            time.sleep(0.01)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)


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
    if directory.is_dir():
        for p in directory.glob(".pos-*"):
            with contextlib.suppress(OSError):
                if at.timestamp() - p.stat().st_mtime > EXPIRE_DAYS * 86400:
                    p.unlink()
        for p in directory.glob(".tmp.*.part"):  # left by a write that died before its rename
            with contextlib.suppress(OSError):
                if at.timestamp() - p.stat().st_mtime > TMP_MAX_AGE:
                    p.unlink()
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
    if not 3 <= len(text) <= 600 or text[0] in "</" or re.match(r"error[: ]", text, re.I):
        return False
    return bool(CUE_RE.search(text[:80].replace("’", "'")))


def result_text(block):
    content = block.get("content")
    if isinstance(content, list):
        content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return content if isinstance(content, str) else ""


def first_tokens(cmd):
    """First word of each pipeline or && segment, path prefix and env assignments dropped."""
    out = []
    for seg in re.split(r"&&|\|\||[;|]", cmd):
        words_ = [w for w in seg.split() if not re.match(r"\w+=", w)]
        if words_ and words_[0] == "rtk" and len(words_) > 1:
            words_ = words_[1:]
        if words_:
            out.append(words_[0].rsplit("/", 1)[-1])
    return out


def path_args(cmd):
    return {w.strip("\"'") for w in cmd.split()[1:]
            if not w.startswith("-") and ("/" in w or re.search(r"\.\w{1,5}$", w))}


def norm_cmd(cmd):
    """The command without leading `cd <dir> &&`, env assignments and sudo/time/nohup/env/rtk."""
    s = cmd.strip()
    while s:
        m = re.match(r"cd\s+\S+\s*(?:&&|;)\s*", s)
        if m:
            s = s[m.end():]
            continue
        head, _, rest = s.partition(" ")
        if re.match(r"[A-Za-z_]\w*=\S*\Z", head) or head in WRAPPERS:
            s = rest.strip()
            continue
        break
    return s


def cmd_name(cmd):
    """Plain command name of a normalised command, or None when it is not one."""
    toks = norm_cmd(cmd).split()
    name = toks[0].rsplit("/", 1)[-1] if toks else ""
    if re.search(r"\d", name) and not DIGIT_NAME_RE.match(name):
        return None
    return name if NAME_RE.match(name) and token_ok(name) else None


def brief(cmd):
    """`<command> <first argument>` for a known subcommand or value-less flag, else the command name alone."""
    name = cmd_name(cmd)
    toks = norm_cmd(cmd).split()
    if name and name not in NAME_ONLY and len(toks) > 1:
        arg = toks[1]
        if (SUB_RE.match(arg) and arg in SUBCMDS) or (FLAG_RE.match(arg) and token_ok(arg)):
            return name + " " + arg
    return name


def related(failed, worked):
    """The retry is the same tool family or touches the same path; anything else is a coincidence."""
    a, b = cmd_name(failed), cmd_name(worked)
    if not a or not b or "cd" in (a, b):
        return False
    a, b = (re.sub(r"^python3\.\d+\Z", "python3", n) for n in (a, b))
    if a == b or any(a in f and b in f for f in FAMILIES):
        return True
    return bool(path_args(norm_cmd(failed)) & path_args(norm_cmd(worked)))


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
            if text and is_correction(text) and text_ok(text):
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
                    err = lines_[0] if lines_ else body.splitlines()[0]
                    quiet = QUIET_CMDS & (set(first_tokens(cmd)) | {cmd_name(cmd)})
                    odd = not all(token_ok(x) for x in norm_cmd(cmd).split())
                    failed = None if quiet or odd or cmd_name(cmd) in (None, "cd") or NOISE_LINE_RE.match(err) else (
                        cmd, err, clean_ts(e.get("timestamp") or session_time))
                else:
                    if failed and cmd != failed[0] and not b.get("is_error") and related(failed[0], cmd):
                        parts = [collapse(failed[1], 100)] if text_ok(failed[1]) else []
                        if brief(cmd):
                            parts.append("worked: " + brief(cmd))
                        ctx = collapse(" | ".join(parts), CONTEXT_MAX)
                        if not is_secret(failed[0] + " " + cmd + " " + ctx):
                            yield {"type": "failure", "signal": brief(failed[0]), "context": ctx,
                                   "time": failed[2]}
                    failed = None


def read_pos(directory, session):
    try:
        parts = pos_path(directory, session).read_text().split()
        return int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
    except (OSError, ValueError, IndexError):
        return 0, 0, 0


def scan(transcript, offset):
    """Complete lines from `offset`: (bytes, new offset), or None for a non-regular file.

    Reads in BLOCK-sized pieces and never holds more than SCAN_MAX bytes. A line with
    no newline within SCAN_MAX is skipped in bounded blocks;
    at end of file the offset moves to the end so the next Stop does not rescan it.
    """
    st = os.stat(transcript)
    if not stat.S_ISREG(st.st_mode):
        return None
    if st.st_size < offset:
        offset = 0
    with open(transcript, "rb") as fh:
        fh.seek(offset)
        buf = bytearray()
        while len(buf) < SCAN_MAX:
            blk = fh.read(min(BLOCK, SCAN_MAX - len(buf)))
            if not blk:
                break
            buf += blk
        end = buf.rfind(b"\n") + 1
        if end:
            return bytes(buf[:end]), offset + end
        if len(buf) < SCAN_MAX:  # a partial last line: wait for its newline
            return b"", offset
        pos = offset + len(buf)
        del buf
        while True:
            blk = fh.read(BLOCK)
            if not blk:
                return b"", pos
            i = blk.find(b"\n")
            if i >= 0:
                return b"", pos + i + 1
            pos += len(blk)


def record(root, session, transcript):
    directory = qdir(root)
    ensure_dir(directory)
    sweep(directory)
    offset, recorded, fails = read_pos(directory, session)
    got = scan(transcript, offset)
    if got is None:
        return
    chunk, new_offset = got
    lines = [x.decode("utf-8", errors="replace") for x in chunk.split(b"\n")]
    signals = list(extract(lines, stamp(now())))
    with locked(directory, wait=RECORD_WAIT):
        recorded, fails = merge(directory, session, signals, recorded, fails)
        write_private(pos_path(directory, session), "%d %d %d\n" % (new_offset, recorded, fails))


def merge(directory, session, signals, recorded, fails):
    """Fold signals into the queue; returns the session's (recorded, fails). Call under locked().

    Corrections go first and may evict the weakest queued failure at the cap, so
    failures cannot starve them; a session adds at most FAIL_MAX failures.
    """
    items = queued(directory)
    for s in sorted(signals, key=lambda s: s["type"] != "correction"):
        sid = signal_id(s["signal"])
        existing = load(directory / (sid + ".json"))
        if existing:
            if existing.get("status") != "queued" or [session, s["time"]] in existing.get("seen", []):
                continue
            existing["count"] = int(existing.get("count", 1)) + 1
            existing["last_seen"] = max(existing.get("last_seen", ""), s["time"])
            existing["seen"] = (existing.get("seen", []) + [[session, s["time"]]])[-SEEN_MAX:]
            save(directory, existing)
            continue
        if recorded >= N_SESSION or (s["type"] == "failure" and fails >= FAIL_MAX):
            continue
        if len(items) >= QUEUE_MAX:
            weak = sorted((e for e in items if e.get("type") == "failure"),
                          key=lambda e: (e["count"], e["last_seen"]))
            if s["type"] != "correction" or not weak:
                continue
            with contextlib.suppress(OSError):
                (directory / (weak[0]["id"] + ".json")).unlink()
            items = [e for e in items if e["id"] != weak[0]["id"]]
        entry = {"schema": 1, "id": sid, "type": s["type"], "signal": s["signal"],
                 "context": s["context"], "status": "queued", "session": session,
                 "time": s["time"], "last_seen": s["time"], "count": 1,
                 "seen": [[session, s["time"]]], "resolved": None, "applied_to": None, "note": ""}
        save(directory, entry)
        items.append(entry)
        recorded += 1
        fails += s["type"] == "failure"
    return recorded, fails


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


def rule_body(line):
    return line.split(" | evidence: ")[0].split(" | applies when: ")[0].strip()


def split_physical(data):
    """Physical lines of a file: split on b"\\n" only. Returns (lines, ends_with_newline)."""
    parts = data.split(b"\n")
    if parts[-1] == b"":
        return parts[:-1], True
    return parts, False


def physical_text(raw):
    return raw.decode("utf-8", errors="replace").rstrip("\r")


def insert_position(text, heading):
    """Index at which a new bullet goes in section `heading`, or a refusal reason."""
    at = None
    fenced = False
    trail = {}  # heading level -> name, for the headings above this one
    for i, raw in enumerate(text):
        if raw.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and raw.rstrip() == heading:
            at = i
            break
        elif not fenced and raw.startswith("#"):
            level = len(raw) - len(raw.lstrip("#"))
            trail = {k: v for k, v in trail.items() if k < level}
            trail[level] = raw.lstrip("#").strip().lower().split(" ")[0]
    if at is None:
        return "section not found: " + heading
    own = len(heading) - len(heading.lstrip("#"))
    if any(v in BLOCKED_SECTIONS for k, v in trail.items() if k < own):
        return "section is inside Gates or Release"
    last, fenced, j = None, False, at + 1
    while j < len(text):
        raw = text[j]
        if raw.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and raw.startswith("#"):
            break
        if not fenced and raw.startswith("- "):
            last = j
        j += 1
    if last is None:
        return at + 1 + (1 if at + 1 < len(text) and not text[at + 1].strip() else 0)
    pos = last + 1
    while pos < len(text) and text[pos][:1] in (" ", "\t") and text[pos].strip():
        pos += 1
    return pos


def cmd_apply(root, pid, fname, section, line):
    directory = qdir(root)
    if not ID_RE.match(pid):
        return refuse("id must be 12 hex characters")
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
    if not EVIDENCE_RE.search(line):
        return refuse("line needs typed evidence: path:, cmd: or correction:")
    checker = rules_checker()
    if checker is not None:
        parsed = checker.parse_rule_line(line + "\n")
        state, why = checker.check_rule(parsed, root) if parsed else ("malformed", "not a rule bullet")
        if state == "malformed":
            return refuse("line is malformed: " + why)
    try:
        with locked(directory):
            entry = load(directory / (pid + ".json"))
            if not entry or entry.get("status") != "queued":
                return refuse("id %s is %s" % (pid, entry.get("status") if entry else "unknown"))
            return write_rule(directory, entry, root, name, heading, line)
    except TimeoutError:
        return refuse("queue is busy, try again")


def write_fd(fd, data):
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)


def write_rule(directory, entry, root, name, heading, line):
    path = Path(root) / ".harness" / name
    if not path.is_file():
        return refuse("missing " + str(path))
    target = path.resolve()
    lines, ends = split_physical(target.read_bytes())
    text = [physical_text(x) for x in lines]
    if text and text[0].startswith("\ufeff"):  # match headings past a BOM; the bytes keep it
        text[0] = text[0][1:]
    if rule_body(line) in [rule_body(x) for x in text]:
        return refuse("line already present")
    if len(lines) + 1 > HARNESS_CAPS[name]:
        return refuse("%s is at its %d-line cap" % (name, HARNESS_CAPS[name]))
    pos = insert_position(text, heading)
    if isinstance(pos, str):
        return refuse(pos)
    terminated = lines if ends else lines[:-1]
    crlf = sum(x.endswith(b"\r") for x in terminated) * 2 > len(terminated)
    new = list(lines)
    at_end = pos == len(lines) and not ends
    if at_end and crlf and new and not new[-1].endswith(b"\r"):
        new[-1] += b"\r"  # the old last line gains its terminator, nothing else moves
    new.insert(pos, line.encode("utf-8") + (b"\r" if crlf and not at_end else b""))
    out = b"\n".join(new) + (b"\n" if ends else b"")
    fd, tmp = tempfile.mkstemp(prefix=".tmp.", suffix="." + name, dir=str(target.parent))
    try:
        write_fd(fd, out)
        os.chmod(tmp, stat.S_IMODE(target.stat().st_mode))
        back, _ = split_physical(Path(tmp).read_bytes())
        if len(back) != len(lines) + 1 or back[pos] != new[pos] or back[:pos] + back[pos + 1:] != new[:pos] + new[pos + 1:]:
            return refuse("write verification failed")
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    placed, _ = split_physical(target.read_bytes())
    if [physical_text(x) for x in placed].count(line) != 1:
        return refuse("line not present after write")
    entry.update(status="approved", resolved=stamp(now()), applied_to="%s:%d" % (name, pos + 1))
    save(directory, entry)
    print("applied to %s:%d" % (name, pos + 1))
    return 0


def cmd_mark(root, pid, note):
    directory = qdir(root)
    if not ID_RE.match(pid):
        return refuse("id must be 12 hex characters")
    entry = load(directory / (pid + ".json"))
    if not entry:
        return refuse("unknown id " + pid)
    if entry.get("status") != "queued":
        return refuse("id %s is %s" % (pid, entry.get("status")))
    try:
        with locked(directory):
            entry = load(directory / (pid + ".json"))
            if not entry or entry.get("status") != "queued":
                return refuse("id %s is %s" % (pid, entry.get("status") if entry else "unknown"))
            entry.update(status="dropped", resolved=stamp(now()), note=collapse(note or "", NOTE_MAX))
            save(directory, entry)
    except TimeoutError:
        return refuse("queue is busy, try again")
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
