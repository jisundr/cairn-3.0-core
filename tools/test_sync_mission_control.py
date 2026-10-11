import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_mission_control as sm  # noqa: E402


def make_src(tmp_path):
    src = tmp_path / "mc"
    (src / "static" / "assets").mkdir(parents=True)
    for name in sm.RUNTIME_FILES:
        (src / name).write_text(name)
    (src / "static" / "index.html").write_text("html")
    (src / "static" / "assets" / "a.js").write_text("js")
    (src / "test_db.py").write_text("tests do not ship")
    (src / "frontend").mkdir()
    (src / "frontend" / "package.json").write_text("{}")
    return src


def test_sync_copies_only_runtime_files(tmp_path):
    src, dst = make_src(tmp_path), tmp_path / "out"
    sm.sync(src, dst)
    shipped = {p.relative_to(dst).as_posix() for p in dst.rglob("*") if p.is_file()}
    assert shipped == set(sm.RUNTIME_FILES) | {"static/index.html", "static/assets/a.js"}


def test_check_detects_edit_missing_and_extra(tmp_path):
    src, dst = make_src(tmp_path), tmp_path / "out"
    sm.sync(src, dst)
    assert sm.stale(src, dst) == []
    (dst / "db.py").write_text("edited")
    (dst / "server.py").unlink()
    (dst / "test_db.py").write_text("stray")
    assert sorted(sm.stale(src, dst)) == ["db.py", "server.py", "test_db.py"]


def test_sync_is_idempotent_and_removes_extras(tmp_path):
    src, dst = make_src(tmp_path), tmp_path / "out"
    sm.sync(src, dst)
    (dst / "stray.py").write_text("x")
    assert sm.sync(src, dst) == ["stray.py"]
    assert sm.sync(src, dst) == []


def test_check_ignores_pycache(tmp_path):
    src, dst = make_src(tmp_path), tmp_path / "out"
    sm.sync(src, dst)
    (dst / "__pycache__").mkdir()
    (dst / "__pycache__" / "db.cpython-313.pyc").write_bytes(b"x")
    assert sm.stale(src, dst) == []
