#!/usr/bin/env python3
"""Copies mission-control's runtime files from the submodule at the repo root
into plugin/mission-control/, so an install carries a standalone copy with no
submodule, tests or frontend source. stdlib only.

Usage:
    python tools/sync_mission_control.py          sync, then list what changed
    python tools/sync_mission_control.py --check  exit 1 if the copy is stale
"""
import argparse
import shutil
import sys
from pathlib import Path

RUNTIME_FILES = (
    "backfill.py", "db.py", "interfaces.py", "parser.py", "pricing.py",
    "pricing_check.py", "prices.json", "server.py", "tasks.py",
)
RUNTIME_DIRS = ("static",)
SRC_DIR = "mission-control"
DST_DIR = "plugin/mission-control"


def wanted(src: Path) -> dict[str, Path]:
    """Relative destination path -> source file, for everything that ships."""
    out = {name: src / name for name in RUNTIME_FILES}
    for d in RUNTIME_DIRS:
        for f in sorted((src / d).rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                out[f.relative_to(src).as_posix()] = f
    return out


def stale(src: Path, dst: Path) -> list[str]:
    """Relative paths missing, different, or present in dst but not shipped."""
    files = wanted(src)
    bad = [rel for rel, f in files.items()
           if not (dst / rel).is_file() or (dst / rel).read_bytes() != f.read_bytes()]
    if dst.is_dir():
        bad += [p.relative_to(dst).as_posix() for p in sorted(dst.rglob("*"))
                if p.is_file() and "__pycache__" not in p.parts
                and p.relative_to(dst).as_posix() not in files]
    return bad


def sync(src: Path, dst: Path) -> list[str]:
    changed = stale(src, dst)
    files = wanted(src)
    for rel in changed:
        target = dst / rel
        if rel in files:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(files[rel], target)
        else:
            target.unlink()
    for d in sorted((p for p in dst.rglob("*") if p.is_dir()), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()
    return changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    root = Path(__file__).resolve().parent.parent
    src, dst = root / SRC_DIR, root / DST_DIR
    if not (src / "server.py").is_file():
        print(f"{SRC_DIR}/ is empty: run `git submodule update --init`", file=sys.stderr)
        return 2
    if ap.parse_args().check:
        bad = stale(src, dst)
        for rel in bad:
            print(f"stale: {rel}")
        return 1 if bad else 0
    for rel in sync(src, dst):
        print(f"synced: {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
