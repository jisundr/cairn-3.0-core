import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402
import pricing_check  # noqa: E402

from test_pricing import make_call  # noqa: E402


def _seed(root: Path, *models: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    conn = db.connect(root / ".cairn")
    try:
        for i, model in enumerate(models):
            db.insert_call(conn, make_call(request_id=f"r-{i}", model=model))
        conn.commit()
    finally:
        conn.close()
    return root


def test_unpriced_model_is_detected(tmp_path):
    root = _seed(tmp_path / "p", "known", "mystery")
    assert pricing_check.unpriced_models([root], {"known": {}}) == {"mystery"}


def test_fully_priced_project_is_empty(tmp_path):
    root = _seed(tmp_path / "p", "known")
    assert pricing_check.unpriced_models([root], {"known": {}}) == set()


def test_project_without_db_is_skipped(tmp_path):
    (tmp_path / "bare").mkdir()
    assert pricing_check.unpriced_models([tmp_path / "bare"], {}) == set()


def test_one_failing_project_does_not_abort_others(tmp_path, monkeypatch):
    bad = _seed(tmp_path / "bad", "x")
    good = _seed(tmp_path / "good", "mystery")
    real = db.connect

    def flaky(cairn_dir):
        if Path(cairn_dir).parent == bad:
            raise RuntimeError("locked")
        return real(cairn_dir)

    monkeypatch.setattr(db, "connect", flaky)
    assert pricing_check.unpriced_models([bad, good], {}) == {"mystery"}


def _setup(tmp_path, *models):
    local = _seed(tmp_path / "local", *models)
    kp = tmp_path / "known-projects.json"
    kp.write_text(json.dumps([]))
    return local, kp, tmp_path / "state" / "pricing-check-state.json"


def test_same_day_does_not_rescan(tmp_path, monkeypatch, capsys):
    local, kp, state = _setup(tmp_path, "mystery")
    state.parent.mkdir()
    state.write_text(json.dumps({"last_checked": "2026-09-29"}))
    calls = []
    monkeypatch.setattr(pricing_check, "unpriced_models", lambda *a, **k: calls.append(a) or set())
    pricing_check.maybe_run(kp, local, state, today="2026-09-29")
    assert calls == []
    assert capsys.readouterr().err == ""


def test_new_day_rescans_and_restamps(tmp_path, monkeypatch):
    local, kp, state = _setup(tmp_path)
    state.parent.mkdir()
    state.write_text(json.dumps({"last_checked": "2026-09-28"}))
    calls = []
    monkeypatch.setattr(pricing_check, "unpriced_models", lambda *a, **k: calls.append(a) or set())
    pricing_check.maybe_run(kp, local, state, today="2026-09-29")
    assert len(calls) == 1
    assert json.loads(state.read_text()) == {"last_checked": "2026-09-29"}


def test_warns_once_naming_model_then_silent_same_day(tmp_path, capsys):
    local, kp, state = _setup(tmp_path, "claude-unpriced-9")
    pricing_check.maybe_run(kp, local, state, today="2026-09-29")
    assert "claude-unpriced-9" in capsys.readouterr().err
    pricing_check.maybe_run(kp, local, state, today="2026-09-29")
    assert capsys.readouterr().err == ""


def test_no_warning_when_all_priced(tmp_path, capsys):
    local, kp, state = _setup(tmp_path, "claude-sonnet-5")
    pricing_check.maybe_run(kp, local, state, today="2026-09-29")
    assert capsys.readouterr().err == ""
    assert json.loads(state.read_text())["last_checked"] == "2026-09-29"
