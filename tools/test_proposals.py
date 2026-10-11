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


def test_signal_is_collapsed_and_long_text_is_dropped_whole(proj):
    record(proj, [user("No,   use\ttabs\n   here")])
    assert [e["signal"] for e in queue(proj)] == ["No, use tabs here"]
    record(proj, [user("No, use tabs\n" + "word " * 100)], session="s2", name="u.jsonl")
    assert len(queue(proj)) == 1
    at_cap = ("No, " + "ab " * 98)[:300].rstrip()
    assert 290 < len(at_cap) <= pr.SIGNAL_MAX
    record(proj, [user(at_cap)], session="s3", name="v.jsonl")
    assert len(queue(proj)) == 2 and all(len(e["signal"]) <= pr.SIGNAL_MAX for e in queue(proj))


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


def fail_ok(n, bad="make tset", good="make test"):
    return bash_pair("f%d" % n, bad, "Exit code 2\nerr %d" % n, True) + bash_pair("g%d" % n, good, "ok", False)


def test_corrections_rank_before_failures_within_a_session(proj):
    pairs = []
    for i in range(4):
        pairs += fail_ok(i, "make tset%d" % i, "make test%d" % i)
    record(proj, pairs + [user("No, use thing %d instead" % i) for i in range(4)])
    types = sorted(e["type"] for e in queue(proj))
    assert types == ["correction"] * 4 + ["failure"]


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


EV = " | evidence: correction:2026-10-11 x"
OK = "- ok" + EV


@pytest.mark.parametrize("kwargs,reason", [
    ({"line": "- Use tabs\n- and more"}, "one physical"),
    ({"line": "- Use tabs"}, "typed evidence"),
    ({"line": "- Use tabs | evidence: because I said so"}, "typed evidence"),
    ({"line": "- Use tabs | evidence: correction:"}, "typed evidence"),
    ({"line": "Use tabs"}, "one physical"),
    ({"line": "- Use kebab-case names" + EV}, "already present"),
    ({"line": "- x | evidence: correction:2026-13-45 bad"}, "malformed"),
    ({"line": OK, "section": "## Nope"}, "section not found"),
    ({"line": OK, "section": "## Gates"}, "Gates or Release"),
    ({"line": OK, "section": "## Release"}, "Gates or Release"),
    ({"line": OK, "section": "### Sub"}, "inside Gates or Release"),
    ({"line": OK, "file": "other.md"}, "must be one of"),
    ({"line": OK, "file": "../x/standards.md"}, "must be one of"),
])
def test_apply_refusals_leave_everything_untouched(proj, kwargs, reason):
    (proj / ".harness/standards.md").write_text(STANDARDS + "\n### Sub\n- nested gate\n")
    record(proj, [user("No, use tabs")])
    (e,) = queue(proj)
    before = harness_bytes(proj)
    args = dict({"line": OK}, **kwargs)
    r = apply(proj, e["id"], **args)
    assert r.returncode == 1 and reason in r.stdout
    assert harness_bytes(proj) == before and queue(proj)[0]["status"] == "queued"


def test_apply_refuses_at_line_cap_and_unknown_or_resolved_id(proj):
    path = proj / ".harness/environment.md"
    path.write_text(HEADER + "## Run\n" + "".join("- r%d\n" % i for i in range(30 - 3)), encoding="utf-8")
    assert len(path.read_text().splitlines()) == 30
    record(proj, [user("No, use tabs")])
    (e,) = queue(proj)
    r = apply(proj, e["id"], "- one more" + EV, section="## Run", file="environment.md")
    assert r.returncode == 1 and "cap" in r.stdout
    assert apply(proj, "000000000000", OK).returncode == 1
    run("mark", "--root", proj, e["id"], "dropped")
    assert apply(proj, e["id"], OK).returncode == 1


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


ALLOW_BENIGN = [
    "No, use pnpm test not npm test",
    "No, the keyboard layout is wrong",
    "No, use camelCase for IDs",
    "No, put it in src/app/page.tsx",
    "No, run mkdir -p before",
    "No, use --filter @scope/pkg",
    "Don't use npm, use pnpm",
    "No, the docs live in docs/schemas/state-v1.md",
]
# (text, the fragment that must not reach a stored field)
TEXT_LEAKS = [
    ("No, send Cookie: sid=abc123xyz with it", "abc123xyz"),
    ("No, Set-Cookie: sid=abc123xyz is wrong", "abc123xyz"),
    ("No, run export FOO=hunter2x first", "hunter2x"),
    ("No, FOO=bar123 make test is wrong", "bar123"),
    ("No, pass: letmein", "letmein"),
    ("No, pass=letmein99", "letmein99"),
    ("No, pw: Tr0ub4dor", "Tr0ub4dor"),
    ("No, the passphrase is purple monkey", "purple"),
    ("No, run gpg --passphrase abc", "passphrase"),
    ("No, run sshpass -p mypw ssh host", "mypw"),
    ("No, run docker login -u bob -p s3cr3tpw", "s3cr3tpw"),
    ("No, run mysql -h db -u root -p Sup3rpw", "Sup3rpw"),
    ("No, run openssl enc -k mypass", "mypass"),
    ("No, run curl --user bob:pw1", "pw1"),
    ("No, use glpat-abcdefghij1234567890", "abcdefghij1234567890"),
    ("No, use SG.abcdefghijklmnop.qrstuvwxyz", "qrstuvwxyz"),
    ("No, use sk-abcdefghij\nklmnopqrstuvwx", "klmnopqrstuvwx"),
    ("No, deploy staging --creds hunter2hunter2", "hunter2hunter2"),
    ("No, the card is 4111111111111111", "4111111111111111"),
    ("No, the card is 4111 1111 1111 1111", "4111 1111"),
    ("No, FOO=hunter2x make test", "hunter2x"),
    ("No, login bob:pw1abc", "pw1abc"),
    ("No, the user is bob@mail.example.com", "mail.example"),
    ("No, the value is Zx9Qw7Er5Ty3Ui1Op", "Zx9Qw7Er5Ty3Ui1Op"),
]
CMD_LEAKS = [
    ("FOO=hunter2x make test", "hunter2x"),
    ("cd app && DB=pw123abc make test", "pw123abc"),
    ("deploy staging --creds hunter2hunter2", "hunter2hunter2"),
    ("sudo time login bob:pw1abc", "pw1abc"),
    ("curl --user bob:pw1 https://x.test", "pw1"),
    ("export FOO=bar123", "bar123"),
    ("openssl enc -k mypass", "mypass"),
]
ERR_LEAKS = [
    ("Set-Cookie: sid=abc123xyz", "abc123xyz"),
    ("pass: letmein", "letmein"),
    ("login failed for bob:pw1abc", "pw1abc"),
    ("bad value 'Zx9Qw7Er5Ty3Ui1Op'", "Zx9Qw7Er5Ty3Ui1Op"),
]


def stored_bytes(proj):
    d = proj / ".cairn/proposals"
    return b"".join(p.read_bytes() for p in d.iterdir() if p.is_file())


@pytest.mark.parametrize("text,secret", TEXT_LEAKS)
def test_allow_list_drops_new_text_leaks_whole(proj, text, secret):
    assert not pr.text_ok(text)
    record(proj, [user(text)])
    assert queue(proj) == [] and secret.encode() not in stored_bytes(proj)


@pytest.mark.parametrize("cmd,secret", CMD_LEAKS)
def test_failure_commands_never_store_the_secret(proj, cmd, secret):
    pair = bash_pair("c", cmd, "Exit code 2\nboom", True) + bash_pair("d", cmd + " ok", "ok", False)
    record(proj, pair)
    assert secret.encode() not in stored_bytes(proj)


@pytest.mark.parametrize("err,secret", ERR_LEAKS)
def test_error_line_leaks_leave_context_empty_but_signal_records(proj, err, secret):
    pair = bash_pair("a", "make deploy", "Exit code 2\n" + err, True) + bash_pair("b", "make build", "ok", False)
    record(proj, pair)
    (e,) = queue(proj)
    assert e["signal"] == "make deploy" and e["context"] == "worked: make build"
    assert secret.encode() not in stored_bytes(proj)


@pytest.mark.parametrize("text", ALLOW_BENIGN)
def test_allow_list_keeps_ordinary_corrections(proj, text):
    assert pr.text_ok(text)
    record(proj, [user(text)])
    assert [e["signal"] for e in queue(proj)] == [text]


@pytest.mark.parametrize("tok", ["pnpm", "package.json", "src/app/page.tsx", "v1.2.3", "snake_case",
                                 "camelCase", "docker-compose.yml", "@scope/pkg", "--dry-run", "-x", "42", "don't"])
def test_allow_list_tokens_that_pass(tok):
    assert pr.token_ok(tok)


@pytest.mark.parametrize("tok", ["a=b", "https://x.test", "user@host.io", "pass:letmein", "$HOME", "--k=v",
                                 "1234567", "aB3dE6gH9jK2mN5pQ8", "abcdefghijklmnopqrstuvwxyz", "x/" + "a1" * 30,
                                 "Zx9Qw7Er5Ty3", "a1b2c3d4e5f6", 'say"hi', "@a.b/c.d/e"])
def test_allow_list_tokens_that_fail(tok):
    assert not pr.token_ok(tok)


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
    (e,) = queue(proj)
    assert e["signal"] == "psql prod" and e["context"] == "worked: psql staging"


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


def _peak_rss_script(path):
    return ("import importlib.util, resource, sys, time\n"
            "spec = importlib.util.spec_from_file_location('p', %r)\n"
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
            "t = time.monotonic()\n"
            "m.record(sys.argv[1], 's', sys.argv[2])\n"
            "print(time.monotonic() - t, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)\n" % str(path))


@pytest.mark.skipif(shutil.which("truncate") is None, reason="truncate missing")
def test_huge_line_without_newline_stays_bounded_and_is_not_rescanned(proj):
    big = proj / "big.jsonl"
    subprocess.run(["truncate", "-s", "1G", str(big)], check=True)
    out = subprocess.run(["python3", "-c", _peak_rss_script(SCRIPT), str(proj), str(big)],
                         capture_output=True, text=True, timeout=60)
    secs, rss = map(float, out.stdout.split())
    rss_mb = rss / (1 << 20 if os.uname().sysname == "Darwin" else 1 << 10)
    assert secs < 2 and rss_mb < 100, (secs, rss_mb)
    off, _ = (proj / ".cairn/proposals/.pos-s").read_text().split()[:2]
    assert int(off) == big.stat().st_size
    with open(big, "ab") as fh:
        fh.write(b"\n" + json.dumps(user("No, use tabs")).encode() + b"\n")
    pr.record(proj, "s", big)
    assert [e["signal"] for e in queue(proj)] == ["No, use tabs"]


def test_oversized_line_followed_by_lines_skips_to_next_newline(proj, monkeypatch):
    monkeypatch.setattr(pr, "SCAN_MAX", 300)
    monkeypatch.setattr(pr, "BLOCK", 64)
    tp = write(proj / "t.jsonl", [user("x " * 500), user("No, use tabs")])
    pr.record(proj, "s", tp)
    pr.record(proj, "s", tp)
    assert [e["signal"] for e in queue(proj)] == ["No, use tabs"]


def test_fifo_and_directory_transcripts_return_at_once(proj):
    fifo = proj / "pipe"
    os.mkfifo(fifo)
    for target in (fifo, proj):
        t = time.monotonic()
        r = subprocess.run(["python3", str(SCRIPT), "record", "--root", str(proj), "--session", "s",
                            "--transcript", str(target)], capture_output=True, text=True, timeout=10)
        assert r.returncode == 0 and r.stdout == "" and time.monotonic() - t < 2
    assert queue(proj) == []


@pytest.mark.parametrize("bad", ["grep -r foo src", "/usr/bin/egrep x y", "rg needle", "diff a b", "test -f x",
                                 "[ -d x ]", "find . -name x", "which node", "command -v jq", "type foo",
                                 "ls missing", "cat missing.txt", "cd src && grep x y", "cat f | grep x",
                                 "rtk grep x", "FOO=1 grep x y"])
def test_quiet_commands_are_not_failures(proj, bad):
    record(proj, fail_ok(1, bad, bad.split()[-1] + " ok"))
    assert queue(proj) == []


def test_failure_needs_a_related_success(proj):
    record(proj, fail_ok(1, "make tset", "git status"), session="a", name="a.jsonl")
    assert queue(proj) == []
    record(proj, fail_ok(2, "python3 run.py src/app.py", "pytest src/app.py"), session="b", name="b.jsonl")
    assert [e["signal"] for e in queue(proj)] == ["python3 run.py"]


def test_error_text_and_rtk_hint_are_not_signals(proj):
    record(proj, [user("Error: tool call failed, no more tries"), user("Error no such file")])
    pair = bash_pair("a", "make tset", "Exit code 2\n[rtk] hint: use rtk make", True) + \
        bash_pair("b", "make test", "ok", False)
    record(proj, pair, session="r", name="r.jsonl")
    assert queue(proj) == []


def test_at_most_two_failures_per_session_across_passes(proj):
    tp = proj / "t.jsonl"
    entries = []
    for i in range(3):
        entries += fail_ok(i, "make tset%d" % i, "make test%d" % i)
    write(tp, entries)
    run("record", "--root", proj, "--session", "s1", "--transcript", tp)
    assert [e["type"] for e in queue(proj)] == ["failure"] * 2
    with open(tp, "a") as fh:
        for e in fail_ok(7, "make tsetx", "make testx"):
            fh.write(json.dumps(e) + "\n")
    run("record", "--root", proj, "--session", "s1", "--transcript", tp)
    assert len(queue(proj)) == 2


def _fill(proj, kind, n):
    d = proj / ".cairn/proposals"
    for i in range(n):
        pr.save(d, {"schema": 1, "id": "%012x" % i, "type": kind, "signal": "old %s %d" % (kind, i),
                    "context": "", "status": "queued", "session": "x", "time": ts(i), "last_seen": ts(i),
                    "count": 1, "seen": [], "resolved": None, "applied_to": None, "note": ""})


def test_correction_evicts_oldest_failure_at_the_cap(proj):
    _fill(proj, "failure", pr.QUEUE_MAX)
    record(proj, [user("No, brand new thing")])
    q = queue(proj)
    assert len(q) == pr.QUEUE_MAX
    assert sum(e["type"] == "correction" for e in q) == 1
    assert not (proj / ".cairn/proposals" / ("%012x.json" % (pr.QUEUE_MAX - 1))).exists()


def test_failure_never_evicts_a_correction_at_the_cap(proj):
    _fill(proj, "correction", pr.QUEUE_MAX)
    record(proj, fail_ok(1))
    assert {e["type"] for e in queue(proj)} == {"correction"} and len(queue(proj)) == pr.QUEUE_MAX


def test_queue_dirs_are_0700_and_files_0600(proj):
    cairn = proj / ".cairn"
    (cairn / "proposals").mkdir(parents=True)
    os.chmod(cairn, 0o755)
    os.chmod(cairn / "proposals", 0o755)
    record(proj, [user("No, use tabs")])
    mode = lambda p: p.stat().st_mode & 0o777
    assert mode(cairn) == 0o700 and mode(cairn / "proposals") == 0o700
    files = [p for p in (cairn / "proposals").iterdir() if p.is_file()]
    assert any(p.suffix == ".json" for p in files) and any(p.name.startswith(".pos-") for p in files)
    assert {mode(p) for p in files} == {0o600}
    (e,) = queue(proj)
    run("mark", "--root", proj, e["id"], "dropped")
    assert mode(cairn / "proposals" / (e["id"] + ".json")) == 0o600


def test_session_id_cannot_escape_the_queue_directory(proj):
    record(proj, [user("No, use tabs")], session="../../evil/ses sion")
    d = proj / ".cairn/proposals"
    pos = [p.name for p in d.glob(".pos-*")]
    assert len(pos) == 1 and "/" not in pos[0] and " " not in pos[0]
    assert not (proj / "evil").exists() and not (proj.parent / "evil").exists()
    record(proj, [user("No, use tabs")], session="x" * 300, name="u.jsonl")
    assert max(len(p.name) for p in d.glob(".pos-*")) <= len(".pos-") + 64


def test_old_pos_files_are_swept_with_expiry(proj):
    d = proj / ".cairn/proposals"
    d.mkdir(parents=True)
    old, fresh = d / ".pos-old", d / ".pos-fresh"
    old.write_text("0 0 0\n")
    fresh.write_text("0 0 0\n")
    when = time.time() - 31 * 86400
    os.utime(old, (when, when))
    pr.sweep(d)
    assert not old.exists() and fresh.exists()


@pytest.mark.parametrize("bad", ["../../evil", "ABCDEF123456", "0123456789a", "0123456789abc", ""])
def test_ids_are_validated_before_use(proj, bad):
    assert run("mark", "--root", proj, bad, "dropped").returncode == 1
    r = apply(proj, bad, OK)
    assert r.returncode == 1 and "12 hex" in r.stdout


def test_transcript_timestamps_are_clamped(proj):
    far_past = (datetime.now(timezone.utc) - timedelta(days=4000)).strftime("%Y-%m-%dT%H:%M:%SZ")
    far_future = (datetime.now(timezone.utc) + timedelta(days=4000)).strftime("%Y-%m-%dT%H:%M:%SZ")
    record(proj, [user("No, use tabs", when=far_past), user("Stop, wrong branch", when=far_future)])
    now_ = datetime.now(timezone.utc)
    for e in queue(proj):
        t = datetime.strptime(e["last_seen"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        assert now_ - timedelta(days=366) <= t <= now_ + timedelta(days=1, minutes=1)


@pytest.mark.skipif(shutil.which("jq") is None or os.geteuid() == 0, reason="needs jq and a non-root user")
def test_hook_is_silent_on_a_read_only_cairn_dir(proj):
    (proj / "CLAUDE.md").write_text("<!-- cairn:start -->\n")
    d = proj / ".cairn/proposals"
    d.mkdir(parents=True)
    os.chmod(proj / ".cairn", 0o500)
    os.chmod(d, 0o500)
    try:
        r = subprocess.run([str(HOOK), "count"], input=json.dumps({"session_id": "n", "cwd": str(proj)}),
                           capture_output=True, text=True, env=dict(os.environ, CLAUDE_PLUGIN_ROOT=str(ROOT / "plugin")))
    finally:
        os.chmod(proj / ".cairn", 0o700)
        os.chmod(d, 0o700)
    assert r.returncode == 0 and r.stderr == ""


@pytest.mark.parametrize("bad,good,signal", [
    ("pnpm test", "npm test", "pnpm test"),
    ("pip install x", "pip3 install x", "pip install"),
    ("python main.py", "python3.12 main.py", "python main.py"),
    ("node build.js", "bun build.js", "node build.js"),
    ("docker build .", "podman build .", "docker build"),
    ("make all", "gmake all", "make all"),
    ("FOO=1 cd x && npm test", "yarn test", "npm test"),
    ("cd foo && make", "cd bar && make", "make"),
    ("sudo time make deploy", "make build", "make deploy"),
])
def test_retry_in_the_same_tool_family_is_recorded(proj, bad, good, signal):
    record(proj, fail_ok(1, bad, good))
    assert [e["signal"] for e in queue(proj)] == [signal]


@pytest.mark.parametrize("bad,good", [
    ("git status", "ls"),
    ("npm test", "pip install x"),
    ("make all", "docker build ."),
    ("grep -r x src", "grep -r y src"),
    ("cd foo", "cd bar"),
    ("cd foo", "make"),
    ("make", "cd foo && ls"),
])
def test_unrelated_or_quiet_commands_are_not_paired(proj, bad, good):
    record(proj, fail_ok(1, bad, good))
    assert queue(proj) == []


def test_apply_crlf_without_trailing_newline_adds_no_bare_cr(proj):
    old = (HEADER + "## Naming\n- Use kebab-case names\n- a").replace("\n", "\r\n").encode()
    assert not old.endswith(b"\n")
    new = apply_to(proj, old).read_bytes()
    assert new == old + b"\r\n" + NEW_LINE.encode() and not new.endswith(b"\r")
    rules_check(proj)


def test_apply_finds_a_heading_behind_a_bom(proj):
    old = ("﻿## Naming\n- Use kebab-case names\n\n## Gates\n- run the gate\n").encode("utf-8")
    assert old.startswith(b"\xef\xbb\xbf")
    new = apply_to(proj, old).read_bytes()
    assert new.startswith(b"\xef\xbb\xbf## Naming") and delta(old, new) == NEW_LINE.encode()


def test_apply_refuses_when_the_written_bytes_do_not_verify(proj, monkeypatch):
    path = proj / ".harness/standards.md"
    before = path.read_bytes()
    record(proj, [user("No, use tabs")])
    (e,) = queue(proj)

    def corrupt(fd, data):
        i = data.index(b"Use tabs")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data[:i] + b"X" + data[i + 1:])
    monkeypatch.setattr(pr, "write_fd", corrupt)
    out = subprocess_free_apply(proj, e["id"])
    assert out == 1
    assert path.read_bytes() == before and queue(proj)[0]["status"] == "queued"
    assert not list((proj / ".harness").glob(".tmp*"))


def subprocess_free_apply(proj, pid):
    return pr.cmd_apply(str(proj), pid, "standards.md", "## Naming", NEW_LINE)
