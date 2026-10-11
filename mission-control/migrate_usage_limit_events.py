#!/usr/bin/env python3
"""One-time migration: purge false-positive `usage_limit_events` rows.

`isApiErrorMessage: true` is Claude Code's generic "an API-level error
occurred inline in this transcript" marker, not a usage-limit-specific one
(see `parser.py`'s `parse_transcript`). Earlier versions of that function
recorded every such entry as a `usage_limit_events` row regardless of
`message` shape, seeding false positives (`model_not_found`,
`oauth_org_not_allowed`, `server_error`, empty-provider-response glitches,
etc.) into every project's `tokens.db`. A genuine usage-limit notice has
`message` as a plain string starting with `"Claude usage limit reached"`;
everything else `isApiErrorMessage` currently flags is a synthetic
assistant-turn object, not a distinct top-level notice.

This re-checks each existing row's own `raw_entry` against that corrected
classification and deletes what doesn't match - no transcript re-parse
needed, since `raw_entry` already holds the original JSON entry.

Usage:
    from migrate_usage_limit_events import run
    run(project_roots=[Path("/some/project"), ...])

Or from the command line, against this project plus every project listed
in `known-projects.json` (via `server.discover_projects`):
    python3 migrate_usage_limit_events.py
"""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402
import server  # noqa: E402

log = logging.getLogger(__name__)


def is_genuine_usage_limit_entry(raw_entry: str) -> bool:
    """True only for the real usage-limit notice shape: `message` is a
    plain string starting with `"Claude usage limit reached"`. Mirrors
    `parser.py`'s `parse_transcript` classification. A `raw_entry` that
    isn't even valid JSON can't be a genuine transcript entry either.
    """
    try:
        parsed = json.loads(raw_entry)
    except json.JSONDecodeError:
        return False
    message = parsed.get("message") if isinstance(parsed, dict) else None
    return isinstance(message, str) and message.startswith("Claude usage limit reached")


def migrate_project(cairn_dir: Path) -> dict:
    """Deletes every `usage_limit_events` row in `cairn_dir/tokens.db` whose
    `raw_entry` doesn't match the genuine usage-limit shape. Returns
    `{"checked": n, "deleted": n, "kept": n}`. Caller is responsible for
    confirming `tokens.db` already exists before calling this (see `run`) -
    `db.connect` would otherwise create an empty one for a project that
    never had any events.
    """
    conn = db.connect(cairn_dir)
    try:
        rows = conn.execute("SELECT id, raw_entry FROM usage_limit_events").fetchall()
        to_delete = [row_id for row_id, raw_entry in rows if not is_genuine_usage_limit_entry(raw_entry)]
        if to_delete:
            conn.executemany("DELETE FROM usage_limit_events WHERE id = ?", [(i,) for i in to_delete])
            conn.commit()
        return {"checked": len(rows), "deleted": len(to_delete), "kept": len(rows) - len(to_delete)}
    finally:
        conn.close()


def run(project_roots: list[Path]) -> dict:
    """Runs `migrate_project` for each root in `project_roots` that already
    has a `.cairn/tokens.db`, skipping the rest and de-duplicating roots. A
    single project's failure doesn't abort the others. Returns
    `{root: {"checked", "deleted", "kept"}}` for every root actually
    migrated.
    """
    results = {}
    seen: set[Path] = set()
    for candidate in project_roots:
        root = Path(candidate).resolve()
        if root in seen:
            continue
        seen.add(root)

        cairn_dir = root / ".cairn"
        if not db.db_path(cairn_dir).exists():
            continue
        try:
            results[root] = migrate_project(cairn_dir)
        except Exception:
            log.warning("migrate_usage_limit_events: skipping project %s", root, exc_info=True)
    return results


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    # This file lives at <cairn-2.0>/mission-control/migrate_usage_limit_events.py;
    # `server.discover_projects` wants the project root cairn itself is
    # installed at, i.e. this file's grandparent.
    local_root = Path(__file__).resolve().parent.parent
    projects = server.discover_projects(local_root)
    results = run([project.root for project in projects])

    totals = {"checked": 0, "deleted": 0, "kept": 0}
    for root, counts in results.items():
        print(f"{root}: checked={counts['checked']} deleted={counts['deleted']} kept={counts['kept']}")
        for key in totals:
            totals[key] += counts[key]
    print(f"TOTAL: checked={totals['checked']} deleted={totals['deleted']} kept={totals['kept']}")


if __name__ == "__main__":
    main()
