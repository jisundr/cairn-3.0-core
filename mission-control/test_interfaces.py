#!/usr/bin/env python3
"""Mock-based tests locking each `interfaces.py` contract's call shape.

No real implementation exists yet (later phases add one per interface).
Each test builds an autospec'd mock from the Protocol, calls it with the
exact keyword shape a real caller will eventually use, and asserts the
mock recorded that call — this fails if a signature silently drifts from
the call shape locked in here, even with nothing behind the interface.
"""
from pathlib import Path
from unittest.mock import create_autospec

from interfaces import (
    BackfillInterface,
    DBInterface,
    ParserInterface,
    PricingInterface,
    ServerInterface,
)


def test_db_interface_call_shape():
    db = create_autospec(DBInterface, instance=True)
    cairn_dir = Path("/tmp/example/.cairn")
    conn = object()

    db.connect(cairn_dir=cairn_dir)
    db.insert_call(conn=conn, row={"request_id": "req-1", "model": "claude"})
    db.has_session(conn=conn, session_id="sess-1")

    assert db.connect.call_args.kwargs == {"cairn_dir": cairn_dir}
    assert db.insert_call.call_args.kwargs == {
        "conn": conn,
        "row": {"request_id": "req-1", "model": "claude"},
    }
    assert db.has_session.call_args.kwargs == {"conn": conn, "session_id": "sess-1"}


def test_parser_interface_call_shape():
    parser = create_autospec(ParserInterface, instance=True)
    cairn_dir = Path("/tmp/example/.cairn")
    transcript_path = Path("/tmp/example/transcript.jsonl")

    parser.parse_session(
        cairn_dir=cairn_dir, transcript_path=transcript_path, session_id="sess-1"
    )

    assert parser.parse_session.call_args.kwargs == {
        "cairn_dir": cairn_dir,
        "transcript_path": transcript_path,
        "session_id": "sess-1",
    }


def test_pricing_interface_call_shape():
    pricing = create_autospec(PricingInterface, instance=True)
    row = {"model": "claude-x", "input_tokens": 100, "output_tokens": 50}
    rows = [row]

    pricing.call_cost(row=row)
    pricing.group_cost(rows=rows)

    assert pricing.call_cost.call_args.kwargs == {"row": row}
    assert pricing.group_cost.call_args.kwargs == {"rows": rows}


def test_backfill_interface_call_shape():
    backfill = create_autospec(BackfillInterface, instance=True)
    known_projects = [Path("/tmp/a"), Path("/tmp/b")]
    local_project = Path("/tmp/local")

    backfill.run(known_projects=known_projects, local_project=local_project)

    assert backfill.run.call_args.kwargs == {
        "known_projects": known_projects,
        "local_project": local_project,
    }


def test_server_interface_call_shape():
    server = create_autospec(ServerInterface, instance=True)
    cairn_dir = Path("/tmp/example/.cairn")

    server.start(cairn_dir=cairn_dir, host="localhost", port=0)
    server.stop()

    assert server.start.call_args.kwargs == {
        "cairn_dir": cairn_dir,
        "host": "localhost",
        "port": 0,
    }
    assert server.stop.call_args.kwargs == {}
