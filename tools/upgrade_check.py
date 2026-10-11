#!/usr/bin/env python3
"""Check that a 2.0 repo's harness survives the 3.0 hooks and scripts untouched.

    python tools/upgrade_check.py [--repo DIR] [--doctor]

Copies DIR's .harness/, CLAUDE.md and docs/tasks/ (default: the committed
fixture tools/fixtures/upgrade-2.0) into a temp dir, hashes every file, runs
the 3.0 scripts over the copy with CLAUDE_PLUGIN_ROOT pointing at a temp
plugin dir whose version is read from plugin/.claude-plugin/plugin.json,
then hashes again. It checks that:

  - rules-check.py exits 0, reports no malformed rule, and counts rules
    without evidence as legacy (a harness with no bullet rules passes as
    "0 rules"; one that has rules but reports none as legacy is a miss);
  - state_schema.py passes over docs/tasks/ (skipped when there are none);
  - session-start.sh prints "cairn updated 0.51.16 -> <version>" once;
  - signals.sh record queues one proposal for a one-correction transcript
    and count announces it;
  - every copied file is byte-identical afterwards, and nothing new appears
    outside .cairn/.

Exercised: hooks/session-start.sh, hooks/signals.sh (record and count),
task-assets/assets/rules-check.py and tools/state_schema.py. Not covered in
CI: hooks/stop-mc.sh, hooks/subagent-marker.sh, hooks/allow-plugin-read.sh,
proposals.py apply and mark, /cairn-setup, /cairn-retro. --doctor runs
/cairn-doctor through `claude` by hand; CI does not.

Exit 0 when every check holds, 1 with one line per miss. The jq-dependent
steps are skipped when jq is absent and CI is unset; with CI set they fail.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent
PLUGIN = CORE / "plugin"
FIXTURE = CORE / "tools" / "fixtures" / "upgrade-2.0"
TARGET = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())["version"]
PREVIOUS = "0.51.16"
SKIP_DIRS = {".cairn"}
CORRECTION = '{"type":"user","message":{"content":"No, use tabs here"}}\n'


def digest(root):
    """Map of relative path -> sha256 for every file outside .cairn/."""
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_file() and not (set(rel.parts) & SKIP_DIRS):
            out[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def judge_counts(counts):
    """(note, miss) for a rules-check counts dict; exactly one is non-empty."""
    total = sum(counts.values())
    if counts["malformed"]:
        return "", f"rules-check.py reports {counts['malformed']} malformed rules"
    if total == 0:
        return "rules-check.py: exit 0, 0 rules (0 legacy), 0 malformed, nothing failed", ""
    if counts["legacy"] == 0:
        return "", f"rules-check.py reports {total} rules and none legacy for a 2.0 harness"
    return f"rules-check.py: exit 0, {counts['legacy']} legacy, 0 malformed, nothing failed", ""


def run(cmd, env, cwd=None, stdin=None, timeout=300):
    return subprocess.run(cmd, env=env, cwd=cwd, input=stdin, text=True,
                          capture_output=True, timeout=timeout)


def check(repo, doctor=False):
    """Return (notes, misses): what held, and one line per miss."""
    notes, misses = [], []
    repo = Path(repo)
    if not (repo / ".harness").is_dir():
        return notes, [f"{repo}: no .harness/ to check"]
    claude_md = repo / "CLAUDE.md"
    text = claude_md.read_text(encoding="utf-8", errors="replace") if claude_md.is_file() else ""
    if "<!-- cairn:start -->" not in text:
        return notes, [f"{repo}: CLAUDE.md missing or without the cairn marker"]

    jq_ok = shutil.which("jq") is not None
    if not jq_ok and os.environ.get("CI"):
        misses.append("jq is not on PATH and CI is set")
    jq_run = jq_ok

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        proj, home, plug = tmp / "proj", tmp / "home", tmp / "plugin"
        proj.mkdir()
        home.mkdir()
        shutil.copytree(repo / ".harness", proj / ".harness")
        shutil.copy2(repo / "CLAUDE.md", proj / "CLAUDE.md")
        tasks = repo / "docs" / "tasks"
        if tasks.is_dir():
            shutil.copytree(tasks, proj / "docs" / "tasks")
        (plug / ".claude-plugin").mkdir(parents=True)
        (plug / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "cairn", "version": TARGET}))
        (plug / "skills").symlink_to(PLUGIN / "skills")
        (plug / "hooks").symlink_to(PLUGIN / "hooks")

        before = digest(proj)
        env = dict(os.environ, HOME=str(home), CLAUDE_PLUGIN_ROOT=str(plug))
        assets = PLUGIN / "skills" / "task-assets" / "assets"

        r = run([sys.executable, str(assets / "rules-check.py"), "--root", str(proj), "--json"], env)
        if r.returncode != 0:
            misses.append(f"rules-check.py exited {r.returncode}: {r.stderr.strip()[:120]}")
        else:
            note, miss = judge_counts(json.loads(r.stdout)["counts"])
            (misses if miss else notes).append(miss or note)

        if tasks.is_dir() and any((proj / "docs" / "tasks").rglob("STATE.md")):
            r = run([sys.executable, str(CORE / "tools" / "state_schema.py"), str(proj / "docs" / "tasks")], env)
            if r.returncode != 0:
                misses.append(f"state_schema.py exited {r.returncode}: {r.stdout.strip()[:160]}")
            else:
                notes.append("state_schema.py: docs/tasks passes schema 1")

        sid = "upgrade-check"
        hook_in = json.dumps({"session_id": sid, "cwd": str(proj)})
        if jq_run:
            (proj / ".cairn").mkdir()
            (proj / ".cairn" / "sessions.log").write_text(f"2026-01-01T00:00:00Z\t{PREVIOUS}\told-session\n")
            r = run([str(PLUGIN / "hooks" / "session-start.sh")], env, stdin=hook_in)
            want = f"cairn updated {PREVIOUS} -> {TARGET}."
            if want not in r.stdout:
                misses.append(f"session-start.sh did not print '{want}': {r.stdout.strip()[:120]!r}")
            else:
                r2 = run([str(PLUGIN / "hooks" / "session-start.sh")], env, stdin=hook_in)
                if "cairn updated" in r2.stdout:
                    misses.append("session-start.sh printed the update notice twice")
                else:
                    notes.append(f"session-start.sh: prints 'cairn updated {PREVIOUS} -> {TARGET}' once")

            tp = tmp / "transcript.jsonl"
            tp.write_text(CORRECTION)
            sig_in = json.dumps({"session_id": sid, "cwd": str(proj), "transcript_path": str(tp)})
            sig = str(PLUGIN / "hooks" / "signals.sh")
            run([sig, "record"], env, stdin=sig_in)
            queued = [p for p in (proj / ".cairn" / "proposals").glob("*.json")
                      if '"status":"queued"' in p.read_text()]
            if len(queued) != 1:
                misses.append(f"signals.sh record queued {len(queued)} proposals, expected 1")
            else:
                r = run([sig, "count"], env, stdin=sig_in)
                if not r.stdout.startswith("cairn: 1 "):
                    misses.append(f"signals.sh count printed {r.stdout.strip()[:80]!r}")
                else:
                    notes.append("signals.sh: one correction queued and announced")
        else:
            notes.append("jq absent: session-start.sh and signals.sh steps skipped")

        if doctor:
            r = run(["claude", "--plugin-dir", str(PLUGIN), "-p", "/cairn-doctor",
                     "--allowedTools", "Bash(python3:*)"], env=dict(os.environ), cwd=proj, timeout=600)
            if r.returncode != 0 or not r.stdout.strip():
                misses.append(f"/cairn-doctor run failed (exit {r.returncode}): {r.stderr.strip()[:120]}")
            else:
                notes.append("/cairn-doctor output:\n" + r.stdout.strip())

        after = digest(proj)
        for rel, h in before.items():
            if rel not in after:
                misses.append(f"{rel}: removed")
            elif after[rel] != h:
                misses.append(f"{rel}: changed")
        for rel in after:
            if rel not in before:
                misses.append(f"{rel}: new file outside .cairn/")
        if not any(m.endswith((": removed", ": changed")) or "new file" in m for m in misses):
            n = sum(1 for k in before if k.startswith(".harness/"))
            notes.append(f"byte-identical: {n} .harness files, {len(before)} files in all, nothing new outside .cairn/")
    return notes, misses


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", default=str(FIXTURE))
    ap.add_argument("--doctor", action="store_true")
    a = ap.parse_args(argv)
    notes, misses = check(a.repo, a.doctor)
    for n in notes:
        print(f"ok   {n}")
    for m in misses:
        print(f"MISS {m}")
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
