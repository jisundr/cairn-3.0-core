#!/usr/bin/env python3
"""Check and select harness rules; the format is in rule-format.md.

    rules-check.py [--root DIR] [--json] [--select PATH... [--kind K]]

Default: scan the four harness files under DIR/.harness/ and print a summary
plus one line per rule that is not verified. Always exits 0 (read-only, never
blocks); an internal error exits 2. --select prints the rules that load for a
task touching PATH... of kind K (default build).
"""
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

FILES = ("architecture.md", "standards.md", "environment.md", "workflow.md")
SKIP_RE = re.compile(r"(gates|release)\b")
PRECOND_RE = re.compile(r"-\s+\[(blocking|warning)\]", re.I)
KINDS = ("research", "build", "review")
EV_DELIM = " | evidence: "
TR_DELIM = " | applies when: "
LEGACY_SHOWN = 10
GLOB_CHARS = "*?["


def parse_rule_line(line):
    """Return {text, evidence, trigger} for a bullet line, else None.

    evidence and trigger are None when absent, "" when present but empty.
    A misordered pair leaves the evidence delimiter inside the trigger,
    which trigger_error reports.
    """
    if not line.startswith("- ") or PRECOND_RE.match(line):
        return None
    body = line[2:].rstrip("\n")
    evidence = trigger = None
    if TR_DELIM in body:
        body, _, trigger = body.rpartition(TR_DELIM)
        trigger = trigger.strip()
    if EV_DELIM in body:
        body, _, evidence = body.rpartition(EV_DELIM)
        evidence = evidence.strip()
    return {"text": body.strip(), "evidence": evidence, "trigger": trigger}


def iter_rules(root):
    """Yield rule dicts (with file and line) from the harness files."""
    for name in FILES:
        path = Path(root) / ".harness" / name
        if not path.is_file():
            continue
        fenced = False
        section = ""
        for n, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if raw.lstrip().startswith("```"):
                fenced = not fenced
                continue
            if fenced:
                continue
            if raw.startswith("#"):
                section = raw.lstrip("#").strip().lower()
                continue
            if SKIP_RE.match(section):
                continue
            rule = parse_rule_line(raw)
            if rule is not None:
                rule.update(file=name, line=n)
                yield rule


def trigger_error(trigger):
    """Return a reason string when the trigger is broken, else None."""
    if trigger is None or trigger == "always":
        return None
    if trigger == "":
        return "empty trigger"
    if EV_DELIM in trigger:
        return "evidence must come before applies when"
    for head, kind_list in (("paths:", False), ("kind:", True)):
        if trigger.startswith(head):
            items = [i.strip() for i in trigger[len(head):].split(",")]
            if not items or not all(items):
                return "empty item in " + head
            if kind_list:
                bad = [i for i in items if i not in KINDS]
                if bad:
                    return "unknown kind " + bad[0]
            return None
    return "unknown trigger form"


def _has_glob(value):
    return any(c in value for c in GLOB_CHARS)


def _check_evidence(evidence, root):
    root = Path(root)
    if evidence == "":
        return "malformed", "empty evidence"
    if evidence.startswith("path:"):
        value = evidence[5:].strip()
        if not value or " " in value or value.startswith("/") or ".." in value.split("/"):
            return "malformed", "bad path evidence"
        if _has_glob(value):
            ok = any(True for _ in root.glob(value))
        else:
            ok = (root / value).exists()
        return ("verified", "") if ok else ("stale", "no match for " + value)
    if evidence.startswith("cmd:"):
        manifest, sep, name = evidence[4:].strip().partition("#")
        if not sep or not manifest or not name or " " in manifest or "/" in manifest:
            return "malformed", "cmd evidence needs <manifest>#<name>"
        if manifest == "package.json":
            f = root / manifest
            if not f.is_file():
                return "stale", "package.json missing"
            try:
                scripts = json.loads(f.read_text(encoding="utf-8")).get("scripts", {})
            except (ValueError, AttributeError):
                return "stale", "package.json unreadable"
            if isinstance(scripts, dict) and name in scripts:
                return "verified", ""
            return "stale", "no script " + name
        if manifest in ("Makefile", "makefile", "GNUmakefile"):
            f = root / manifest
            if not f.is_file():
                return "stale", manifest + " missing"
            pattern = re.compile(r"^" + re.escape(name) + r"\s*:(?!=)", re.M)
            if pattern.search(f.read_text(encoding="utf-8", errors="replace")):
                return "verified", ""
            return "stale", "no target " + name
        return "unverifiable", "unsupported manifest " + manifest
    if evidence.startswith("correction:"):
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2}) (\S.*)", evidence[11:].strip())
        if not m:
            return "malformed", "correction needs <YYYY-MM-DD> <text>"
        try:
            date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return "malformed", "bad date"
        return "unverifiable", "correction"
    return "unverifiable", "untyped"


def check_rule(rule, root):
    """Return (state, reason): verified|stale|unverifiable|legacy|malformed."""
    reason = trigger_error(rule.get("trigger"))
    if reason:
        return "malformed", reason
    if EV_DELIM in rule.get("text", ""):
        return "malformed", "more than one evidence item"
    if rule.get("evidence") is None:
        return "legacy", "no evidence"
    return _check_evidence(rule["evidence"], root)


def _glob_regex(glob):
    glob = glob.strip()
    if glob.endswith("/") or not _has_glob(glob):
        glob = glob.rstrip("/") + "/**"
    out = ""
    i = 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif glob.startswith("**", i):
            out += ".*"
            i += 2
        elif glob[i] == "*":
            out += "[^/]*"
            i += 1
        elif glob[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(glob[i])
            i += 1
    return re.compile(out)


def _static_prefix(glob):
    parts = []
    for seg in glob.strip().rstrip("/").split("/"):
        if _has_glob(seg):
            break
        parts.append(seg)
    return "/".join(parts)


def _norm(value):
    """Strip whitespace and leading ./ ; "." alone becomes the root, ""."""
    value = value.strip()
    while value.startswith("./"):
        value = value[2:].lstrip("/")
    return "" if value == "." else value


def relativize(paths, root):
    """Make --select paths root-relative; absolute ones outside root are dropped."""
    base = Path(root).resolve()
    out = []
    for p in paths:
        if p.startswith("/"):
            try:
                rel = Path(p).resolve().relative_to(base).as_posix()
            except ValueError:
                continue
            p = "" if rel == "." else rel + ("/" if p.endswith("/") and rel != "." else "")
        out.append(_norm(p))
    return out


def _glob_hits(glob, path):
    glob = _norm(glob)
    path = _norm(path)
    if path == "":
        return True
    if _glob_regex(glob).fullmatch(path.rstrip("/")) or _glob_regex(glob).fullmatch(path.rstrip("/") + "/x"):
        return True
    if path.endswith("/"):
        pdir = path.rstrip("/")
        static = _static_prefix(glob) if _has_glob(glob) else glob.strip().rstrip("/")
        return (static == pdir or static.startswith(pdir + "/")
                or static == "" or pdir.startswith(static + "/"))
    return False


def matches(rule, paths, kind="build"):
    """True when the rule loads for a task with these paths and kind."""
    trigger = rule.get("trigger")
    if trigger is None or trigger == "always" or trigger_error(trigger):
        return True
    if trigger.startswith("kind:"):
        return kind in [k.strip() for k in trigger[5:].split(",")]
    globs = [g.strip() for g in trigger[6:].split(",")]
    return any(_glob_hits(g, p) for g in globs for p in paths)


def scan(root):
    results = []
    for rule in iter_rules(root):
        state, reason = check_rule(rule, root)
        results.append(dict(rule, state=state, reason=reason))
    return results


def _snip(text):
    return text[:60]


def report(results):
    counts = {s: 0 for s in ("verified", "stale", "unverifiable", "legacy", "malformed")}
    for r in results:
        counts[r["state"]] += 1
    no_trigger = sum(1 for r in results if r["trigger"] is None)
    lines = ["rules: %d (%d verified, %d stale, %d unverifiable, %d legacy, %d malformed); %d without a trigger" % (
        len(results), counts["verified"], counts["stale"], counts["unverifiable"],
        counts["legacy"], counts["malformed"], no_trigger)]
    legacy_seen = 0
    legacy_total = counts["legacy"]
    for state in ("malformed", "stale", "unverifiable", "legacy"):
        for r in results:
            if r["state"] != state:
                continue
            if state == "legacy":
                legacy_seen += 1
                if legacy_seen > LEGACY_SHOWN:
                    continue
            lines.append('%s  %s:%d  %s - "%s"' % (state, r["file"], r["line"], r["reason"], _snip(r["text"])))
    if legacy_total > LEGACY_SHOWN:
        lines.append("+%d more legacy" % (legacy_total - LEGACY_SHOWN))
    return lines, counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--select", nargs="*", metavar="PATH")
    ap.add_argument("--kind", default="build", choices=KINDS)
    args = ap.parse_args(argv)
    results = scan(args.root)
    if args.select is not None:
        select = relativize(args.select, args.root)
        loaded = [r for r in results if matches(r, select, args.kind)]
        if args.json:
            print(json.dumps(loaded, indent=2))
        else:
            print("loads %d of %d rules" % (len(loaded), len(results)))
            for r in loaded:
                print("%s:%d  %s" % (r["file"], r["line"], r["text"]))
        return 0
    lines, counts = report(results)
    if args.json:
        print(json.dumps({"counts": counts, "rules": results}, indent=2))
    else:
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # internal error, distinct from a finding
        print("rules-check: internal error: %s" % exc, file=sys.stderr)
        sys.exit(2)
