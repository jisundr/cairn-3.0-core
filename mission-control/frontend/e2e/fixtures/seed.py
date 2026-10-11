#!/usr/bin/env python3
"""Seeds the Playwright "populated" webServer's fixture project: a
`.cairn/tokens.db` (via db.py's insert helpers, mirroring test_server.py's
`make_project` fixture pattern) plus one transcript `.jsonl` under a
scratch HOME so server.py's on-demand transcript lookup resolves
"available" for one call. Two sessions - one with a saved label and a
usage-limit event (WarningBanner + drilldown coverage), one without a
label (short-id fallback) on an unpriced model (unknown-cost coverage).
Timestamps are relative to the run's current time, not hardcoded, since
server.py's range windows are wall-clock-relative. Also one `docs/tasks/`
folder (Kanban board coverage - a real card to open a real drawer on).

Usage: python3 seed.py <scratch_dir>
`<scratch_dir>/project` becomes the project root passed to server.py;
`<scratch_dir>` is also this webServer's HOME env override, so
`Path.home() / ".claude" / "projects"` resolves under it.
"""
import base64
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

MISSION_CONTROL_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(MISSION_CONTROL_ROOT))
import db  # noqa: E402
import server  # noqa: E402

SESSION_MAIN = "e2e-session-main"
SESSION_OTHER = "e2e-session-other"
SESSION_MAIN_LABEL = "Add a login page to the app"
SESSION_MAIN_CAIRN_VERSION = "0.40.0"
AVAILABLE_REQUEST_ID = "req-available-1"

# 2x2 images encoded by Pillow (libwebp for the WebP, lossless), so a real
# browser decodes both - doc-images.spec.ts asserts naturalWidth > 0.
FIXTURE_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGPUqzViYGBgYgADAAqCAOE9pau+AAAAAElFTkSuQmCC"
FIXTURE_WEBP_B64 = "UklGRh4AAABXRUJQVlA4TBEAAAAvAUAAAAfQvrpUpv+BiOh/AAA="


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_db(project_root: Path, now: datetime) -> None:
    conn = db.connect(project_root / ".cairn")

    calls = [
        dict(
            request_id=AVAILABLE_REQUEST_ID,
            session_id=SESSION_MAIN,
            agent="main",
            model="claude-sonnet-5",
            timestamp=iso(now - timedelta(hours=2)),
            input_tokens=1200,
            output_tokens=600,
        ),
        dict(
            request_id="req-2",
            session_id=SESSION_MAIN,
            agent="builder",
            model="claude-sonnet-5",
            timestamp=iso(now - timedelta(hours=1, minutes=50)),
            input_tokens=800,
            output_tokens=1400,
            cache_read_tokens=200,
        ),
        dict(
            request_id="req-3",
            session_id=SESSION_MAIN,
            agent="reviewer",
            model="claude-opus-5",
            timestamp=iso(now - timedelta(hours=1, minutes=20)),
            input_tokens=400,
            output_tokens=300,
        ),
        # e2e-session-other's one call is on "claude-haiku-4.5", which isn't
        # a key in prices.json (only "claude-haiku-4-5-20251001" is priced)
        # - pricing.call_cost returns "unknown" for it, exercising the
        # info-dot affordance (goal 3) without needing a missing-price
        # backend fixture.
        dict(
            request_id="req-4",
            session_id=SESSION_OTHER,
            agent="main",
            model="claude-haiku-4.5",
            timestamp=iso(now - timedelta(days=2, hours=3)),
            input_tokens=300,
            output_tokens=150,
        ),
    ]
    for call in calls:
        db.insert_call(conn, call)

    tool_uses = [
        dict(
            tool_use_id="tu-1",
            request_id="req-2",
            session_id=SESSION_MAIN,
            agent="builder",
            tool_name="Bash",
            timestamp=iso(now - timedelta(hours=1, minutes=50)),
        ),
        dict(
            tool_use_id="tu-2",
            request_id="req-2",
            session_id=SESSION_MAIN,
            agent="builder",
            tool_name="Read",
            timestamp=iso(now - timedelta(hours=1, minutes=49)),
        ),
        dict(
            tool_use_id="tu-3",
            request_id="req-3",
            session_id=SESSION_MAIN,
            agent="reviewer",
            tool_name="Skill",
            detail="commit-msg-lint",
            timestamp=iso(now - timedelta(hours=1, minutes=19)),
        ),
    ]
    for tool_use in tool_uses:
        db.insert_tool_use(conn, **tool_use)

    # The usage-limit event this whole e2e addition exists to guard: the
    # WarningBanner it drives is where AlertTriangleIcon rendered
    # unconstrained (~800px) before the icon-sizing fix landed - no mockup
    # depicts a usage-limit event, so nothing but a real rendered check
    # (jsdom doesn't do real CSS layout) can catch a regression here.
    db.insert_usage_limit_event(
        conn,
        session_id=SESSION_MAIN,
        timestamp=iso(now - timedelta(hours=1, minutes=45)),
        raw_entry=json.dumps({"isApiErrorMessage": True}),
    )
    db.save_session_label(conn, session_id=SESSION_MAIN, label=SESSION_MAIN_LABEL)
    # Only the main session gets a cairn version; e2e-session-other stands
    # in for a session that predates version capture ("cairn unknown").
    db.save_session_version(conn, session_id=SESSION_MAIN, version=SESSION_MAIN_CAIRN_VERSION)
    conn.commit()
    conn.close()


def seed_transcript(scratch: Path, project_root: Path) -> None:
    claude_projects_dir = scratch / ".claude" / "projects"
    transcript_path = server.transcript_path_for(claude_projects_dir, project_root, SESSION_MAIN)
    transcript_path.parent.mkdir(parents=True, exist_ok=True)

    entries = [
        {"message": {"role": "user", "content": "Add a login page to the app."}},
        {
            "requestId": AVAILABLE_REQUEST_ID,
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "tu-available-1", "name": "Read", "input": {"file_path": "src/login.py"}},
                    {"type": "text", "text": "Sure - adding a login page now."},
                ],
            },
        },
    ]
    with transcript_path.open("w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


KANBAN_TASK_FOLDER = "docs/tasks/2026-01-01-0000-research-e2e-drawer-fixture"

# 05-verification's own parallel-heartbeat scenario (PRD §12 step 9's
# "scripted equivalent" allowance): two real task folders standing in for
# two real parallel Claude Code sessions - kanban-liveness.spec.ts writes a
# subagent marker (`<session>--<agent>.active`) under `~/.claude/cairn/active/` (this webServer's own
# scratch HOME, per tasks.DEFAULT_HEARTBEAT_DIR) naming each folder's
# `(project, task)` pair, ages one past the 4 h marker ceiling, and asserts
# only that one's card drops out of Ongoing.
HEARTBEAT_TASK_FOLDER_A = "docs/tasks/2026-01-03-0000-research-e2e-heartbeat-a"
HEARTBEAT_TASK_FOLDER_B = "docs/tasks/2026-01-03-0000-research-e2e-heartbeat-b"


def seed_task_folder(project_root: Path) -> None:
    """One `docs/tasks/` folder so the Kanban board (goal 11) has a real
    card to open a real drawer on - `research`-kind (tasks.py's `_done_fact`
    never shells out to `gh` for it) so this stays hermetic like every other
    fixture here, no `gh`/network dependency."""
    folder = project_root / KANBAN_TASK_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "STATE.md").write_text(
        "---\n"
        "goal: E2E fixture task folder, used only to exercise the Kanban drawer (§6.7) in a real browser.\n"
        "path: escalated\n"
        "key_info: fixture only, not a live task\n"
        "flags: []\n"
        "---\n"
        "> state read on resume; log below is append-only.\n\n"
        "- 2026-01-01: Fixture folder seeded by seed.py for drawer-sizing e2e coverage.\n"
    )
    # A doc with two relative images (root and subfolder) for
    # doc-images.spec.ts. NOTES.md, not PLAN.md, so the card's column stays put.
    (folder / "NOTES.md").write_text("# Notes\n\n![root image](./x.png)\n\n![mockup image](mockups/y.webp)\n")
    (folder / "x.png").write_bytes(base64.b64decode(FIXTURE_PNG_B64))
    (folder / "mockups").mkdir(exist_ok=True)
    (folder / "mockups" / "y.webp").write_bytes(base64.b64decode(FIXTURE_WEBP_B64))


def seed_heartbeat_task_folders(project_root: Path) -> None:
    """Two more `docs/tasks/` folders, `research`-kind and worded so neither
    `_needs_attention_fact` nor `_done_fact` fires - column here is
    otherwise the `scoping` stage or later, with no attention signal, so `kanban-liveness.spec.ts` can attribute an
    `active` badge verbatim to its own synthetic heartbeat file, not to
    frontmatter wording."""
    for folder_rel, label in ((HEARTBEAT_TASK_FOLDER_A, "a"), (HEARTBEAT_TASK_FOLDER_B, "b")):
        folder = project_root / folder_rel
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "STATE.md").write_text(
            "---\n"
            f"goal: E2E fixture task folder {label}, used only to exercise Kanban heartbeat liveness (§8) in a real browser.\n"
            "path: escalated\n"
            "key_info: fixture only, not a live task\n"
            "flags: []\n"
            "---\n"
            "> state read on resume; log below is append-only.\n\n"
            f"- 2026-01-03: Fixture folder {label} seeded by seed.py for kanban-liveness e2e coverage.\n"
        )


def main() -> None:
    scratch = Path(sys.argv[1]).resolve()
    project_root = scratch / "project"
    project_root.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    seed_db(project_root, now)
    seed_transcript(scratch, project_root)
    seed_task_folder(project_root)
    seed_heartbeat_task_folders(project_root)
    print(project_root)


if __name__ == "__main__":
    main()
