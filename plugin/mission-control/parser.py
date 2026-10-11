#!/usr/bin/env python3
"""Transcript walker for cairn's token-metering feature. stdlib only.

Usage:
    from parser import parse_session
    title = parse_session(cairn_dir, transcript_path, session_id)
"""
import contextlib
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402

AGENT_TOOL_NAMES = {"Agent", "Task"}
AGENT_ID_RE = re.compile(r"agentId:\s*([0-9a-f]+)")

# db.py's `calls.model` column is NOT NULL. A transcript entry missing
# `message.model` (seen in the wild on some malformed captures) must
# never let None through to that insert — record it under this explicit
# sentinel instead, so the row (and its token/cost data) is still kept.
UNKNOWN_MODEL = "(unknown)"

# hooks/session-start.sh appends `<utc>\t<version>\t<session_id>` to
# `.cairn/sessions.log` on every SessionStart. The version field is only
# trusted if it looks like a release number - `unknown` (plugin.json
# unreadable) and anything else fail this match and are skipped. The
# digits are ASCII-only ([0-9], not \d) to match the frontend's compare.
SESSIONS_LOG = "sessions.log"
MAX_VERSION_LEN = 64
CAIRN_VERSION_RE = re.compile(r"[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}(?:[-+][0-9A-Za-z.-]{1,32})?")


def _tool_result_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "\n".join(parts)
    return ""


def _load_entries(path: Path) -> list[dict]:
    entries = []
    if not path.exists():
        return entries
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _extract_ai_title(entries: list[dict]) -> str | None:
    # Claude Code writes an "ai-title" record into the transcript whenever it
    # (re)generates the session's title (the same text shown in the terminal
    # header / resume picker) - a session can have several as the title gets
    # revised, so the last one in file order is the current title.
    title = None
    for entry in entries:
        if entry.get("type") != "ai-title":
            continue
        ai_title = entry.get("aiTitle")
        if ai_title:
            title = ai_title
    return title


def build_agent_map(main_entries: list[dict]) -> dict[str, str]:
    pending = {}
    agent_map = {}
    for entry in main_entries:
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "tool_use" and block.get("name") in AGENT_TOOL_NAMES:
                tool_use_id = block.get("id")
                subagent_type = (block.get("input") or {}).get("subagent_type")
                if tool_use_id and subagent_type:
                    pending[tool_use_id] = subagent_type
            elif block_type == "tool_result":
                tool_use_id = block.get("tool_use_id")
                if tool_use_id in pending:
                    text = _tool_result_text(block.get("content"))
                    match = AGENT_ID_RE.search(text)
                    if match:
                        agent_map[match.group(1)] = pending[tool_use_id]
    return agent_map


def parse_transcript(entries: list[dict], *, session_id: str, agent: str, conn) -> None:
    for entry in entries:
        if entry.get("isApiErrorMessage") is True:
            error_message = entry.get("message")
            if isinstance(error_message, str) and error_message.startswith("Claude usage limit reached"):
                db.insert_usage_limit_event(
                    conn,
                    session_id=session_id,
                    timestamp=entry.get("timestamp"),
                    raw_entry=json.dumps(entry),
                )
            continue

        message = entry.get("message")
        if not isinstance(message, dict):
            continue

        request_id = entry.get("requestId")
        timestamp = entry.get("timestamp")
        usage = message.get("usage")

        if usage is not None and request_id:
            cache_creation = usage.get("cache_creation") or {}
            db.insert_call(
                conn,
                {
                    "request_id": request_id,
                    "session_id": session_id,
                    "agent": agent,
                    "model": message.get("model") or UNKNOWN_MODEL,
                    "timestamp": timestamp,
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                    "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
                    "cache_write_5m_tokens": cache_creation.get("ephemeral_5m_input_tokens", 0),
                    "cache_write_1h_tokens": cache_creation.get("ephemeral_1h_input_tokens", 0),
                },
            )

        if not request_id:
            continue

        content = message.get("content")
        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            tool_name = block.get("name")
            detail = block.get("input", {}).get("skill") if tool_name == "Skill" else None
            db.insert_tool_use(
                conn,
                tool_use_id=block.get("id"),
                request_id=request_id,
                session_id=session_id,
                agent=agent,
                tool_name=tool_name,
                timestamp=timestamp,
                detail=detail,
            )


def _record_cairn_version(conn, cairn_dir: Path, session_id: str) -> None:
    """Copies the cairn version `session_id` started under from
    sessions.log into tokens.db, once. The first valid line for the
    session wins, so a session resumed after a plugin update keeps its
    start version. A missing or unreadable log saves nothing.
    """
    if db.has_session_version(conn, session_id):
        return
    try:
        with (Path(cairn_dir) / SESSIONS_LOG).open(encoding="utf-8") as f:
            for line in f:
                fields = line.rstrip("\n").split("\t")
                if len(fields) != 3 or fields[2] != session_id:
                    continue
                version = fields[1]
                if len(version) <= MAX_VERSION_LEN and CAIRN_VERSION_RE.fullmatch(version):
                    db.save_session_version(conn, session_id=session_id, version=version)
                    return
    except (OSError, UnicodeDecodeError):
        return


def parse_session(cairn_dir: Path, transcript_path: Path, session_id: str) -> str | None:
    transcript_path = Path(transcript_path)
    conn = db.connect(Path(cairn_dir))
    try:
        main_entries = _load_entries(transcript_path)
        agent_map = build_agent_map(main_entries)
        parse_transcript(main_entries, session_id=session_id, agent="main", conn=conn)

        subagents_dir = transcript_path.parent / transcript_path.stem / "subagents"
        if subagents_dir.is_dir():
            for subagent_path in sorted(subagents_dir.glob("agent-*.jsonl")):
                agent_id = subagent_path.stem.removeprefix("agent-")
                agent_name = agent_map.get(agent_id, "unknown")
                sub_entries = _load_entries(subagent_path)
                parse_transcript(sub_entries, session_id=session_id, agent=agent_name, conn=conn)

        title = _extract_ai_title(main_entries)
        if title:
            # Skip the save entirely when this pass found no title, so a
            # previously saved label (from an earlier pass that did) is
            # never wiped out by one that didn't.
            db.save_session_label(conn, session_id=session_id, label=title)

        conn.commit()

        # Token rows are committed above, so a database error while
        # recording the version can only lose the version, never them.
        try:
            _record_cairn_version(conn, Path(cairn_dir), session_id)
            conn.commit()
        except sqlite3.Error:
            # A rollback that fails too (e.g. disk I/O) is dropped: the
            # token rows are already committed, and close() below still runs.
            with contextlib.suppress(sqlite3.Error):
                conn.rollback()
        return title
    finally:
        conn.close()
