#!/usr/bin/env python3
"""Contracts for cairn mission control's future components. stdlib only.

Every class here is a `typing.Protocol` — method signatures only, no
bodies beyond `...`, no logic, no I/O. Real implementations (`db.py`,
`parser.py`, `pricing.py`, `backfill.py`, `server.py`) land in later
phases; this file exists so `test_interfaces.py` can lock each contract's
call shape before any of them exist.

Usage:
    from interfaces import PricingInterface
    # a later phase's pricing.py implements this Protocol structurally —
    # no explicit inheritance required.
"""
from pathlib import Path
from typing import Protocol


class DBInterface(Protocol):
    """Schema + insert helpers over a project's `tokens.db`."""

    def connect(self, cairn_dir: Path):
        """Open (creating if needed) `cairn_dir/tokens.db` and return a
        connection with the current schema applied."""
        ...

    def insert_call(self, conn, row: dict) -> None:
        """Insert one `calls`-shaped row. Idempotent on `request_id`."""
        ...

    def has_session(self, conn, session_id: str) -> bool:
        """True if any row for `session_id` is already recorded."""
        ...


class ParserInterface(Protocol):
    """Transcript walker: transcript -> rows, written via `DBInterface`."""

    def parse_session(
        self, cairn_dir: Path, transcript_path: Path, session_id: str
    ) -> str:
        """Parse one transcript file, write its rows via `db.py`, and
        return the session's title."""
        ...


class PricingInterface(Protocol):
    """Read-time cost lookup. No write path."""

    def call_cost(self, row: dict):
        """Cost in dollars for one `calls`-shaped row, or the string
        `"unknown"` if `row["model"]` has no price entry."""
        ...

    def group_cost(self, rows):
        """Total cost in dollars for an iterable of `calls`-shaped rows,
        or `None` if any row's model is unpriced."""
        ...


class BackfillInterface(Protocol):
    """Enumerates known projects and ingests any session missing from
    that project's own `tokens.db`."""

    def run(self, known_projects: list[Path], local_project: Path) -> None:
        """For `local_project` plus every project in `known_projects`,
        parse and record every session not already present in that
        project's own `tokens.db`. Idempotent; a single project's or
        file's failure doesn't abort the rest."""
        ...


class ServerInterface(Protocol):
    """Stdlib HTTP server + JSON API over `DBInterface`'s tables."""

    def start(self, cairn_dir: Path, host: str = "localhost", port: int = 0) -> int:
        """Start serving `cairn_dir`'s data and return the bound port."""
        ...

    def stop(self) -> None:
        """Stop a server previously started by `start`."""
        ...
