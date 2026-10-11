#!/usr/bin/env python3
"""First-launch cross-project ingestion for cairn's token-metering feature.

stdlib only. Implements `interfaces.BackfillInterface`.

For the launching project plus every project already known to cairn (via
`known-projects.json`, resolved by the caller), finds every session
transcript not yet recorded in that project's own `tokens.db` and parses
it in via `parser.parse_session`. Writes land only inside a target
project's own `.cairn/` - never `known-projects.json`, never another
project's `tokens.db`.

`server.py` never imports this module at its own module level - only
lazily inside `start()` - so importing `server` here (for
`DEFAULT_CLAUDE_PROJECTS_DIR` and `encode_project_path`) stays a one-way
dependency with no import cycle.

Usage:
    from backfill import run
    run(known_projects=[Path("/other/project")], local_project=Path.cwd())
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402
import parser  # noqa: E402
import server  # noqa: E402

log = logging.getLogger(__name__)


def run(
    known_projects: list[Path],
    local_project: Path,
    claude_projects_dir: Path | None = None,
) -> None:
    """For `local_project` plus every project in `known_projects`, parse and
    record every session not already present in that project's own
    `tokens.db`. Idempotent; a single project's or file's failure doesn't
    abort the rest.
    """
    claude_projects_dir = (
        Path(claude_projects_dir) if claude_projects_dir else server.DEFAULT_CLAUDE_PROJECTS_DIR
    )

    roots: list[Path] = []
    seen: set[Path] = set()
    for candidate in [local_project, *known_projects]:
        root = Path(candidate).resolve()
        if root in seen:
            continue
        seen.add(root)
        roots.append(root)

    for root in roots:
        try:
            _backfill_root(root, claude_projects_dir)
        except Exception:
            log.warning("backfill: skipping project %s", root, exc_info=True)


def _backfill_root(root: Path, claude_projects_dir: Path) -> None:
    transcript_dir = claude_projects_dir / server.encode_project_path(root)
    if not transcript_dir.is_dir():
        return

    cairn_dir = root / ".cairn"
    conn = db.connect(cairn_dir)
    try:
        for transcript_path in sorted(transcript_dir.glob("*.jsonl")):
            session_id = transcript_path.stem
            try:
                if db.has_session(conn, session_id):
                    continue
                parser.parse_session(cairn_dir, transcript_path, session_id)
            except Exception:
                log.warning(
                    "backfill: skipping session %s in project %s", session_id, root, exc_info=True
                )
    finally:
        conn.close()
