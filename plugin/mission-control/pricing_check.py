#!/usr/bin/env python3
"""Once-a-day pricing-drift check for cairn's token-metering feature.

stdlib only. Finds every model recorded in any known project's
`tokens.db` that has no entry in `prices.json`, and names them on stderr.
Detection only - it never edits `prices.json` and never derives a rate.

Throttled to one scan per UTC calendar day by a small global state file
(`{"last_checked": "YYYY-MM-DD"}`). Projects are resolved through
`server.discover_projects`, a one-way import (`server` never imports this
module), the same direction `backfill.py` takes.

Usage:
    from pricing_check import maybe_run
    maybe_run(known_projects_path, local_project, state_path)
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402
import pricing  # noqa: E402
import server  # noqa: E402

log = logging.getLogger(__name__)


def today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def unpriced_models(roots: list[Path], prices: dict | None = None) -> set[str]:
    """Models in any root's `tokens.db` that are not keys of `prices`.
    A root with no db yet is skipped; one root's failure doesn't abort the rest.
    """
    prices = pricing.current_prices() if prices is None else prices
    missing: set[str] = set()
    for root in roots:
        cairn_dir = Path(root) / ".cairn"
        if not db.db_path(cairn_dir).exists():
            continue
        try:
            conn = db.connect(cairn_dir)
            try:
                rows = conn.execute("SELECT DISTINCT model FROM calls").fetchall()
            finally:
                conn.close()
        except Exception:
            log.warning("pricing_check: skipping project %s", root, exc_info=True)
            continue
        missing.update(model for (model,) in rows if model not in prices)
    return missing


def _last_checked(state_path: Path) -> str | None:
    try:
        return json.loads(state_path.read_text()).get("last_checked")
    except (OSError, ValueError, AttributeError):
        return None


def _write_state(state_path: Path, today: str) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_name(f"{state_path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps({"last_checked": today}))
    os.replace(tmp, state_path)


def maybe_run(
    known_projects_path: Path,
    local_project: Path,
    state_path: Path,
    today: str | None = None,
) -> None:
    """Scan at most once per UTC day; warn on stderr naming any unpriced model."""
    today = today or today_utc()
    if _last_checked(state_path) == today:
        return
    projects = server.discover_projects(local_project, known_projects_path)
    missing = unpriced_models([p.root for p in projects])
    _write_state(state_path, today)
    if missing:
        print(
            "cairn: models missing from mission-control/prices.json (cost shows unknown): "
            + ", ".join(sorted(missing))
            + " - add their rates to prices.json",
            file=sys.stderr,
        )
