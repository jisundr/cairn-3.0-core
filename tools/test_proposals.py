import importlib.util
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "plugin/skills/task-assets/assets"
SCRIPT = ASSETS / "proposals.py"
HOOK = ROOT / "plugin/hooks/signals.sh"

_spec = importlib.util.spec_from_file_location("proposals", SCRIPT)
pr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pr)

HEADER = "> header\n\n"
STANDARDS = HEADER + "## Naming\n- Use kebab-case names\n- Name tests test_*.py\n\n## Gates\n- run the gate\n"


def ts(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def user(text, when=None, **extra):
    e = {"type": "user", "timestamp": when or ts(), "message": {"role": "user", "content": text}}
    e.update(extra)
    return e


def bash_pair(tid, cmd, result, error):
    use = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": cmd}}]}}
    res = {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tid, "content": result, "is_error": error}]}}
    return [use, res]


def write(path, entries, tail="\n"):
    path.write_text("\n".join(json.dumps(e) for e in entries) + tail, encoding="utf-8")
    return path


@pytest.fixture
def proj(tmp_path):
    h = tmp_path / ".harness"
    h.mkdir()
    (h / "standards.md").write_text(STANDARDS, encoding="utf-8")
    return tmp_path


def run(*args):
    return subprocess.run(["python3", str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def record(proj, entries, session="s1", name="t.jsonl"):
    tp = write(proj / name, entries)
    r = run("record", "--root", proj, "--session", session, "--transcript", tp)
    assert r.returncode == 0
    return tp


def queue(proj):
    return pr.entries(proj / ".cairn" / "proposals")


def harness_bytes(proj):
    return {p.name: p.read_bytes() for p in (proj / ".harness").iterdir()}


def test_one_correction_makes_one_file_and_leaves_harness(proj):
    before = harness_bytes(proj)
    record(proj, [user("No, use pytest instead of unittest here")])
    files = sorted(p.name for p in (proj / ".cairn/proposals").glob("*.json"))
    assert len(files) == 1
    e = queue(proj)[0]
    assert list(e) == list(pr.FIELDS)
    assert (e["type"], e["status"], e["count"], e["schema"]) == ("correction", "queued", 1, 1)
    assert len(e["id"]) == 12 and e["seen"] == [["s1", e["time"]]]
    assert harness_bytes(proj) == before


def test_noise_is_not_a_correction(proj):
    record(proj, [
        user("hello there, please run the tests"),
        user("<command-name>/x</command-name> no"),
        user("no way", isMeta=True),
        user("no way again", isSidechain=True),
        user("no more of this", origin={"kind": "peer"}),
        user("no thanks", promptSource="suggestion_accepted"),
        user("x" * 700 + " no"),
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "z", "content": "no"}]}},
    ])
    assert queue(proj) == []


def test_secret_text_is_skipped(proj):
    record(proj, [user("No, the api key is abc123"), user("don't use token sk-abcdefghijklmnopqrstuv")])
    assert queue(proj) == []


def test_signal_is_collapsed_and_truncated(proj):
    record(proj, [user("No,   use\ttabs\n" + "word " * 100)])
    sig = queue(proj)[0]["signal"]
    assert len(sig) == pr.SIGNAL_MAX and "\n" not in sig and "  " not in sig


def test_cap_of_five_per_session_and_rerun_idempotent(proj):
    entries = [user("No, do thing number %d differently" % i) for i in range(9)]
    tp = record(proj, entries)
    assert len(queue(proj)) == pr.N_SESSION
    run("record", "--root", proj, "--session", "s1", "--transcript", tp)
    assert len(queue(proj)) == pr.N_SESSION
    assert all(e["count"] == 1 for e in queue(proj))


def test_incremental_offset_reads_only_new_lines(proj):
    tp = proj / "t.jsonl"
    write(tp, [user("No, use tabs")])
    run("record", "--root", proj, "--session", "s1", "--transcript", tp)
    with open(tp, "a") as fh:
        fh.write(json.dumps(user("Stop, wrong branch")) + "\n")
    run("record", "--root", proj, "--session", "s1", "--transcript", tp)
    assert len(queue(proj)) == 2 and all(e["count"] == 1 for e in queue(proj))
    pos = (proj / ".cairn/proposals/.pos-s1").read_text().split()
    assert int(pos[0]) == tp.stat().st_size and pos[1] == "2"


def test_line_over_scan_cap_is_skipped_not_stuck(proj, monkeypatch):
    monkeypatch.setattr(pr, "SCAN_MAX", 400)
    tp = write(proj / "t.jsonl", [user("x " * 600), user("No, use tabs")])
    pr.record(proj, "s1", tp)
    assert queue(proj) == []
    pr.record(proj, "s1", tp)
    assert [e["signal"] for e in queue(proj)] == ["No, use tabs"]


def test_partial_last_line_waits_for_next_pass(proj):
    tp = proj / "t.jsonl"
    tp.write_text(json.dumps(user("No, use tabs")) + "\n" + json.dumps(user("Stop, wrong"))[:30])
    run("record", "--root", proj, "--session", "s1", "--transcript", tp)
    assert len(queue(proj)) == 1


def test_later_session_repeat_merges(proj):
    record(proj, [user("No, use tabs")], session="s1")
    record(proj, [user("no use tabs!", when=ts())], session="s2", name="u.jsonl")
    (e,) = queue(proj)
    assert e["count"] == 2 and e["session"] == "s1"
    assert [p[0] for p in e["seen"]] == ["s1", "s2"]


def test_failure_needs_a_different_success(proj):
    only_fail = bash_pair("a", "make test", "Exit code 2\nboom", True)
    record(proj, only_fail, session="f1", name="a.jsonl")
    assert queue(proj) == []
    pair = bash_pair("a", "make tset", "Exit code 2\nNo rule to make target", True) + \
        bash_pair("b", "make test", "ok", False)
    record(proj, pair, session="f2", name="b.jsonl")
    (e,) = queue(proj)
    assert e["type"] == "failure" and e["signal"] == "make tset"
    assert e["context"] == "No rule to make target | worked: make test"


def test_refused_tool_calls_are_not_failures(proj):
    pair = bash_pair("a", "rm x", "The user doesn't want to proceed", True) + \
        bash_pair("b", "ls", "ok", False)
    record(proj, pair)
    assert queue(proj) == []


def test_corrections_rank_before_failures_at_cap(proj):
    fail = bash_pair("a", "bad cmd", "Exit code 1\nerr", True) + bash_pair("b", "good cmd", "ok", False)
    entries = fail + [user("No, use thing %d instead" % i) for i in range(5)]
    record(proj, entries)
    assert {e["type"] for e in queue(proj)} == {"correction"}


def test_queue_cap_stops_new_but_merges_continue(proj):
    d = proj / ".cairn/proposals"
    for i in range(pr.QUEUE_MAX):
        pr.save(d, {"schema": 1, "id": "%012x" % i, "type": "correction", "signal": "old %d" % i,
                    "context": "", "status": "queued", "session": "x", "time": ts(), "last_seen": ts(),
                    "count": 1, "seen": [], "resolved": None, "applied_to": None, "note": ""})
    sid = pr.signal_id("No, brand new thing")
    record(proj, [user("No, brand new thing")])
    assert not (d / (sid + ".json")).exists()
    assert len(queue(proj)) == pr.QUEUE_MAX
    pr.save(d, dict(pr.load(d / ("%012x.json" % 0)), signal="x"))
    first = pr.load(d / ("%012x.json" % 0))
    first["id"] = pr.signal_id("No, same again")
    pr.save(d, first)
    os.remove(d / ("%012x.json" % 0))
    record(proj, [user("No, same again")], session="s9", name="m.jsonl")
    assert pr.load(d / (first["id"] + ".json"))["count"] == 2


def test_expiry_and_tombstone_retention(proj):
    d = proj / ".cairn/proposals"
    base = {"schema": 1, "type": "correction", "context": "", "session": "x", "count": 1, "seen": [],
            "applied_to": None, "note": ""}
    pr.save(d, dict(base, id="a" * 12, signal="old queued", status="queued", time=ts(31),
                    last_seen=ts(31), resolved=None))
    pr.save(d, dict(base, id="b" * 12, signal="fresh queued", status="queued", time=ts(29),
                    last_seen=ts(29), resolved=None))
    pr.save(d, dict(base, id="c" * 12, signal="old dropped", status="dropped", time=ts(100),
                    last_seen=ts(100), resolved=ts(91)))
    pr.save(d, dict(base, id="d" * 12, signal="new dropped", status="dropped", time=ts(80),
                    last_seen=ts(80), resolved=ts(60)))
    assert run("count", "--root", proj).stdout.strip() == "1"
    pr.sweep(d)
    assert sorted(p.stem for p in d.glob("*.json")) == ["b" * 12, "d" * 12]


def test_dropped_and_approved_do_not_resurface(proj):
    record(proj, [user("No, use tabs")])
    (e,) = queue(proj)
    assert run("mark", "--root", proj, e["id"], "dropped", "--note", "not now").returncode == 0
    record(proj, [user("No, use tabs")], session="s2", name="u.jsonl")
    (e2,) = queue(proj)
    assert e2["status"] == "dropped" and e2["count"] == 1 and e2["note"] == "not now"
    assert run("count", "--root", proj).stdout.strip() == "0"


def test_mark_dropped_leaves_harness_byte_identical(proj):
    record(proj, [user("No, use tabs")])
    before = harness_bytes(proj)
    (e,) = queue(proj)
    assert run("mark", "--root", proj, e["id"], "dropped").returncode == 0
    assert harness_bytes(proj) == before
    assert run("mark", "--root", proj, "nope00000000", "dropped").returncode == 1


def apply(proj, pid, line, section="## Naming", file="standards.md"):
    return run("apply", "--root", proj, pid, "--file", file, "--section", section, "--line", line)


def test_apply_adds_exactly_one_line_after_last_bullet(proj):
    record(proj, [user("No, use tabs")])
    (e,) = queue(proj)
    line = "- Use tabs | evidence: correction:2026-10-11 asked once"
    old = (proj / ".harness/standards.md").read_text().splitlines()
    r = apply(proj, e["id"], line)
    assert r.returncode == 0, r.stdout
    new = (proj / ".harness/standards.md").read_text().splitlines()
    assert len(new) == len(old) + 1 and new[5] == line
    assert new[:5] + new[6:] == old
    done = queue(proj)[0]
    assert done["status"] == "approved" and done["applied_to"] == "standards.md:6" and done["resolved"]
    assert not list((proj / ".harness").glob(".tmp*"))
    rules = subprocess.run(["python3", str(ASSETS / "rules-check.py"), "--root", str(proj)],
                           capture_output=True, text=True)
    assert rules.returncode == 0 and "0 malformed" in rules.stdout


@pytest.mark.parametrize("kwargs,reason", [
    ({"line": "- Use tabs\n- and more"}, "one physical"),
    ({"line": "Use tabs"}, "one physical"),
    ({"line": "- Use kebab-case names"}, "already present"),
    ({"line": "- x | evidence: correction:2026-13-45 bad"}, "malformed"),
    ({"line": "- ok", "section": "## Nope"}, "section not found"),
    ({"line": "- ok", "section": "## Gates"}, "Gates or Release"),
    ({"line": "- ok", "section": "## Release"}, "Gates or Release"),
    ({"line": "- ok", "file": "other.md"}, "must be one of"),
    ({"line": "- ok", "file": "../x/standards.md"}, "must be one of"),
])
def test_apply_refusals_leave_everything_untouched(proj, kwargs, reason):
    record(proj, [user("No, use tabs")])
    (e,) = queue(proj)
    before = harness_bytes(proj)
    args = dict({"line": "- ok"}, **kwargs)
    r = apply(proj, e["id"], **args)
    assert r.returncode == 1 and reason in r.stdout
    assert harness_bytes(proj) == before and queue(proj)[0]["status"] == "queued"


def test_apply_refuses_at_line_cap_and_unknown_or_resolved_id(proj):
    path = proj / ".harness/environment.md"
    path.write_text(HEADER + "## Run\n" + "".join("- r%d\n" % i for i in range(30 - 3)), encoding="utf-8")
    assert len(path.read_text().splitlines()) == 30
    record(proj, [user("No, use tabs")])
    (e,) = queue(proj)
    r = apply(proj, e["id"], "- one more", section="## Run", file="environment.md")
    assert r.returncode == 1 and "cap" in r.stdout
    assert apply(proj, "000000000000", "- ok").returncode == 1
    run("mark", "--root", proj, e["id"], "dropped")
    assert apply(proj, e["id"], "- ok").returncode == 1


def test_caps_mirror_budget_gate():
    spec = importlib.util.spec_from_file_location("budget", ROOT / "tools/budget.py")
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    assert pr.HARNESS_CAPS == b.HARNESS_FILE_CAPS


def test_list_orders_hints_duplicates_and_limits(proj):
    (proj / ".harness/standards.md").write_text(
        STANDARDS.replace("- Use kebab-case names", "- Prefer tabs over spaces | evidence: path:x"), encoding="utf-8")
    entries = [user("No, prefer tabs over spaces please")] + \
        [user("Stop, handle case %d separately" % i) for i in range(4)]
    record(proj, entries + [user("Stop, handle case 9 separately")])
    out = run("list", "--root", proj, "--limit", "2").stdout
    assert out.count("\n") >= 2 and "+3 more queued" in out
    full = run("list", "--root", proj, "--limit", "5", "--json").stdout
    items = json.loads(full)["items"]
    tabs = next(i for i in items if "tabs" in i["signal"])
    assert tabs["dup"].startswith("standards.md: Prefer tabs")


def test_bad_or_missing_transcript_exits_zero(proj):
    assert run("record", "--root", proj, "--session", "s", "--transcript", proj / "missing").returncode == 0
    bad = proj / "bad.jsonl"
    bad.write_bytes(b"\xff\xfe not json\n{\n[1]\n\x00\n")
    assert run("record", "--root", proj, "--session", "s", "--transcript", bad).returncode == 0
    assert run("count", "--root", "/nonexistent/x").returncode == 0
    assert queue(proj) == []


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq missing")
def test_shell_count_equals_python_count(proj):
    (proj / "CLAUDE.md").write_text("<!-- cairn:start -->\n")
    record(proj, [user("No, use tabs"), user("Stop, wrong branch"), user("Don't touch the lockfile")])
    d = proj / ".cairn/proposals"
    old = pr.load(sorted(d.glob("*.json"))[0])
    old["last_seen"] = ts(40)
    pr.save(d, old)
    first = pr.load(sorted(d.glob("*.json"))[1])
    first.update(status="dropped", resolved=ts(1))
    pr.save(d, first)
    py = int(run("count", "--root", proj).stdout)
    out = subprocess.run([str(HOOK), "count"], input=json.dumps({"session_id": "n", "cwd": str(proj)}),
                         capture_output=True, text=True, env=dict(os.environ, CLAUDE_PLUGIN_ROOT=str(ROOT / "plugin")))
    assert py == 1
    assert out.returncode == 0 and ("%d rule proposals queued" % py) in out.stdout
    again = subprocess.run([str(HOOK), "count"], input=json.dumps({"session_id": "n", "cwd": str(proj)}),
                           capture_output=True, text=True)
    assert again.stdout == ""


LEAKS = [
    "No, use Authorization: Bearer abc.def.ghi here",
    "don't send the bearer value like that",
    "No, the header is authorization: Basic dXNlcjpwYXNz",
    "no, set pwd=hunter2 in the env",
    "don't connect to postgres://admin:pass@host/db",
    "No, use mysql://root:toor@localhost/app",
    "stop using rk_" "live_" "4eC39HqLyjWDarjtT1zdp7dc",
    "No, the pk_test_TYooMQauvdEDq54NiTphI7jx one",
    "don't paste sk_live_abc123 anywhere",
    "no, the bot token is xoxb-123456789012-abcdefghij",
    "No, post to https://hooks.slack.com/services/T000/B000/XXXX",
    "don't call /v1/export?sig=9f8e7d6c5b4a",
    "No, add ?token=abc to the url",
    "stop appending &secret=zzz",
    "no, the Basic value dXNlcjpwYXNzd29yZA== is wrong",
    "No, log in as root with Winter2026!",
    "don't use AKIAIOSFODNN7EXAMPLE",
    "No, use ghp_abcdefghijklmnopqrstuvwxyz0123456789",
    "no, github_pat_11ABCDEFG0abcdefghijklmnop is expired",
    "don't commit sk-ant-api03-abcdefghijklmnopqrstuvwx",
    "No, set password=letmein",
    "No, the passwd file is wrong",
    "don't print -----BEGIN PRIVATE KEY----- blocks",
    "no, the jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig is wrong",
    "No, the digest 5d41402abc4b2a76b9719d911017c592ae2f6b1c is not that",
    "don't hardcode api_key=abc",
    "No, use the API-KEY header",
    "no, the secret_key should be rotated",
    "No, use the private key at ~/.ssh/id",
    "don't set key: abc123 in yaml",
    "no, the access key is old",
    "No, run curl -u admin:Winter2026! https://x",
    "don't run mysql -uroot -pSup3rS3cret",
    "No, curl -H 'Authorization: Basic dXNlcjpwYXNz' is wrong",
    "stop running psql postgres://u:pw@h/db",
    "No, the credentials are in the vault",
    "don't use Tr0ub4dor3xyz as the value",
]
BENIGN = [
    "No, use tabs instead of spaces",
    "Don't touch the lockfile",
    "No, the keyboard shortcut should be ctrl+k",
    "Stop, the monkey patch is wrong",
    "No, put the config in plugin/skills/task-assets/assets",
    "That's not it, run make test instead",
    "No, use kebab-case for file names",
    "don't call rm -rf, use git clean -fd",
    "No, mkdir -p the directory first",
    "I meant the second branch, actually",
    "No, the primary key column should be id",
    "Stop, use python3 -m pytest tools/",
]


@pytest.mark.parametrize("text", LEAKS)
def test_secret_corpus_leaks_are_dropped(proj, text):
    assert pr.is_secret(text)
    record(proj, [user(text)])
    assert queue(proj) == []


@pytest.mark.parametrize("text", BENIGN)
def test_secret_corpus_benign_text_is_kept(proj, text):
    assert not pr.is_secret(text)
    record(proj, [user(text)])
    assert len(queue(proj)) == 1


def test_corpus_size():
    assert len(LEAKS) >= 30 and len(BENIGN) >= 10


FAIL_CMDS = [
    "curl -u admin:Winter2026! https://example.test/api",
    "mysql -uroot -pSup3rS3cret -e 'select 1'",
    "curl -H 'Authorization: Basic dXNlcjpwYXNz' https://example.test",
    "psql postgres://u:pw@h/db",
    "deploy --token abc123",
]


@pytest.mark.parametrize("cmd", FAIL_CMDS)
def test_failure_with_a_secret_in_its_command_is_dropped(proj, cmd):
    pair = bash_pair("a", cmd, "Exit code 2\nboom", True) + bash_pair("b", cmd.split()[0] + " ok", "ok", False)
    record(proj, pair)
    assert queue(proj) == []


def test_failure_error_line_with_a_secret_is_dropped(proj):
    pair = bash_pair("a", "psql prod", "Exit code 2\nFATAL: could not reach postgres://u:pw@h/db", True) + \
        bash_pair("b", "psql staging", "ok", False)
    record(proj, pair)
    assert queue(proj) == []


def test_failure_stores_command_name_and_first_argument_only(proj):
    pair = bash_pair("a", "make deploy --env=prod --region eu-west-1", "Exit code 2\nno target", True) + \
        bash_pair("b", "make build --env=prod --region eu-west-1 --jobs 4", "ok", False)
    record(proj, pair)
    (e,) = queue(proj)
    assert e["signal"] == "make deploy"
    assert e["context"] == "no target | worked: make build"


NEW_LINE = "- Use tabs | evidence: correction:2026-10-11 asked once"


def rules_check(proj):
    r = subprocess.run(["python3", str(ASSETS / "rules-check.py"), "--root", str(proj)],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "0 malformed" in r.stdout, r.stdout
    return r


def apply_to(proj, content, link=False, mode=None):
    """Write content as standards.md (or as a symlink target), queue one signal, apply NEW_LINE."""
    path = proj / ".harness/standards.md"
    path.unlink()
    if link:
        real = proj / "shared-standards.md"
        real.write_bytes(content)
        path.symlink_to(real)
    else:
        path.write_bytes(content)
        if mode:
            os.chmod(path, mode)
    record(proj, [user("No, use tabs")])
    (e,) = queue(proj)
    r = apply(proj, e["id"], NEW_LINE)
    assert r.returncode == 0, r.stdout
    return (proj / "shared-standards.md") if link else path


def delta(old, new):
    o, n = old.split(b"\n"), new.split(b"\n")
    assert len(n) == len(o) + 1
    for i in range(len(n)):
        if n[i] != o[i]:
            assert n[i + 1:] == o[i:] and n[:i] == o[:i]
            return n[i]
    return n[-1]


def test_apply_keeps_crlf_files_crlf(proj):
    old = STANDARDS.replace("\n", "\r\n").encode()
    new = apply_to(proj, old).read_bytes()
    assert delta(old, new) == NEW_LINE.encode() + b"\r"
    assert new.count(b"\r") == old.count(b"\r") + 1 and new.count(b"\n") == old.count(b"\n") + 1
    rules_check(proj)


def test_apply_leaves_unicode_line_separators_inside_a_bullet(proj):
    odd = "- Name files\u0085with\x0ctabs | evidence: path:x"
    old = (HEADER + "## Naming\n" + odd + "\n- Name tests test_*.py\n\n## Gates\n- run the gate\n").encode()
    new = apply_to(proj, old).read_bytes()
    assert delta(old, new) == NEW_LINE.encode()
    assert odd.encode() in new.split(b"\n")
    rules_check(proj)


def test_apply_without_trailing_newline_keeps_none(proj):
    old = (HEADER + "## Naming\n- Use kebab-case names\n- Name tests test_*.py").encode()
    new = apply_to(proj, old).read_bytes()
    assert not new.endswith(b"\n")
    assert new.split(b"\n")[:-1] == old.split(b"\n") and new.split(b"\n")[-1] == NEW_LINE.encode()
    rules_check(proj)


def test_apply_midfile_without_trailing_newline_is_one_added_line(proj):
    old = (HEADER + "## Naming\n- Use kebab-case names\n\n## Other\n- last bullet").encode()
    new = apply_to(proj, old).read_bytes()
    assert not new.endswith(b"\n") and delta(old, new) == NEW_LINE.encode()
    rules_check(proj)


def test_apply_updates_symlink_target_and_keeps_link(proj):
    old = STANDARDS.encode()
    real = apply_to(proj, old, link=True)
    link = proj / ".harness/standards.md"
    assert link.is_symlink() and link.resolve() == real.resolve()
    assert delta(old, real.read_bytes()) == NEW_LINE.encode()
    assert not list(proj.glob(".tmp*")) and not list((proj / ".harness").glob(".tmp*"))
    rules_check(proj)


def test_apply_lf_file_diff_is_one_line_and_mode_kept(proj):
    old = STANDARDS.encode()
    new = apply_to(proj, old, mode=0o640).read_bytes()
    assert delta(old, new) == NEW_LINE.encode() and (proj / ".harness/standards.md").stat().st_mode & 0o777 == 0o640
    rules_check(proj)


def _apply_worker(args):
    root, pid, line = args
    r = subprocess.run(["python3", str(SCRIPT), "apply", "--root", root, pid, "--file", "standards.md",
                        "--section", "## Naming", "--line", line], capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def test_parallel_applies_lose_no_line_and_duplicate_none(proj):
    from multiprocessing.pool import ThreadPool
    for rnd in range(3):
        before = len((proj / ".harness/standards.md").read_text().splitlines())
        entries = [user("No, use thing %d-%d instead" % (rnd, i)) for i in range(12)]
        for k in range(0, 12, 5):
            record(proj, entries[k:k + 5], session="r%d-%d" % (rnd, k), name="t%d-%d.jsonl" % (rnd, k))
        # standards.md cap is 40 lines; trim between rounds so each round has room
        mine = [e for e in queue(proj) if e["status"] == "queued"]
        assert len(mine) == 12
        jobs = [(str(proj), e["id"], "- Rule %s | evidence: correction:2026-10-11 x" % e["id"]) for e in mine]
        with ThreadPool(12) as pool:
            results = pool.map(_apply_worker, jobs)
        assert all(rc == 0 for rc, _, _ in results), results
        text = (proj / ".harness/standards.md").read_text()
        for e in mine:
            assert text.count("- Rule %s " % e["id"]) == 1
        done = [e for e in queue(proj) if e["status"] == "approved"]
        assert all(("- Rule %s " % e["id"]) in text for e in done)
        # free room: drop the applied rule lines for the next round
        kept = [l for l in text.splitlines() if not l.startswith("- Rule ")]
        (proj / ".harness/standards.md").write_text("\n".join(kept) + "\n")
        for e in mine:
            os.remove(proj / ".cairn/proposals" / (e["id"] + ".json"))
        assert before == len(kept)


def test_parallel_records_do_not_lose_count_updates(proj):
    from multiprocessing.pool import ThreadPool

    def go(i):
        tp = write(proj / ("t%d.jsonl" % i), [user("No, use tabs")])
        return run("record", "--root", proj, "--session", "p%d" % i, "--transcript", tp).returncode

    with ThreadPool(10) as pool:
        assert pool.map(go, range(10)) == [0] * 10
    (e,) = queue(proj)
    assert e["count"] == 10 and len(e["seen"]) == pr.SEEN_MAX


def test_lock_file_fallback_without_fcntl(proj, monkeypatch):
    monkeypatch.setattr(pr, "fcntl", None)
    d = proj / ".cairn/proposals"
    with pr.locked(d):
        assert (d / ".lock.excl").exists()
        with pytest.raises(TimeoutError):
            with pr.locked(d, wait=0.1):
                pass
    assert not (d / ".lock.excl").exists()
