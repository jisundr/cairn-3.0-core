#!/usr/bin/env python3
"""Read-time cost lookup for cairn's token-metering feature. stdlib only.

Prices come from the checked-in `prices.json` table (model -> $/MTok for
input, output, cache_read, cache_write_5m, cache_write_1h) and are applied
here at READ time only, never baked into `calls`/`tool_uses` rows at write
time — a price update is a data edit to `prices.json`, never a migration.

An unrecognized model, or a recognized model missing one of the rate keys
a call actually used, reports cost "unknown" for that call. A rollup group
containing any unpriced model reports cost None for the whole group — never
a silently-partial sum.

Usage:
    import pricing
    pricing.call_cost(row)     # float, or the string "unknown"
    pricing.group_cost(rows)   # float, or None if any row is unpriced
"""
import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

PRICES_FILENAME = "prices.json"

# Token-count fields on a `calls`-shaped row, matching db.py's columns.
_TOKEN_FIELDS = (
    ("input_tokens", "input"),
    ("output_tokens", "output"),
    ("cache_read_tokens", "cache_read"),
    ("cache_write_5m_tokens", "cache_write_5m"),
    ("cache_write_1h_tokens", "cache_write_1h"),
)

UNKNOWN = "unknown"


def prices_path() -> Path:
    return Path(__file__).resolve().parent / PRICES_FILENAME


def load_prices(path: Path | None = None) -> dict:
    with open(path or prices_path()) as f:
        return json.load(f)


# Cached table plus the (mtime_ns, size) it was parsed from. A running server
# sees prices.json edits because the default table is resolved per call.
_cache: dict = {"path": None, "stamp": None, "table": None}


def current_prices(path: Path | None = None) -> dict:
    """The table in `prices.json`, re-parsed only when the file's mtime or
    size changes. A missing/invalid/wrong-shaped file keeps the last good
    table (logging a warning); it never raises. Raises only if the very
    first load has no good table to fall back on.
    """
    path = Path(path or prices_path())
    try:
        st = path.stat()
        stamp = (st.st_mtime_ns, st.st_size)
    except OSError as e:
        log.warning("prices file unreadable, keeping last good table: %s", e)
        stamp = None
    same_file = _cache["path"] == path
    if stamp is not None and not (same_file and _cache["stamp"] == stamp):
        try:
            table = load_prices(path)
            if not isinstance(table, dict) or not all(
                isinstance(v, dict) for v in table.values()
            ):
                raise ValueError("prices must be an object of model -> rates object")
            _cache.update(path=path, stamp=stamp, table=table)
        except (OSError, ValueError) as e:
            log.warning("invalid prices file, keeping last good table: %s", e)
            if same_file:
                _cache["stamp"] = stamp  # don't re-warn until it changes again
    if _cache["table"] is None or _cache["path"] != path:
        raise RuntimeError(f"no valid prices table at {path}")
    return _cache["table"]


def call_cost(row, prices: dict | None = None):
    """Cost in dollars for one `calls`-shaped row, or the string "unknown"
    if `row["model"]` isn't in `prices`, or is in `prices` but missing a
    rate key that this row's nonzero token fields need.
    """
    if prices is None:
        prices = current_prices()
    rates = prices.get(row["model"])
    if rates is None:
        return UNKNOWN

    total_cents_per_mtok = 0.0
    for token_field, rate_key in _TOKEN_FIELDS:
        if rate_key not in rates:
            # A partial rate set (e.g. a model missing cache_write_1h)
            # must never silently price this call at 0 for that field —
            # degrade to "unknown" rather than raising KeyError.
            return UNKNOWN
        total_cents_per_mtok += row.get(token_field, 0) * rates[rate_key]
    return total_cents_per_mtok / 1_000_000


def group_cost(rows, prices: dict | None = None):
    """Total cost in dollars for an iterable of `calls`-shaped rows, or None
    if any row's model is unpriced — never a partial sum over the priced
    rows only.
    """
    if prices is None:
        prices = current_prices()
    total = 0.0
    for row in rows:
        cost = call_cost(row, prices=prices)
        if cost == UNKNOWN:
            return None
        total += cost
    return total
