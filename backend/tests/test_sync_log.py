import logging
import types

import pytest

from tests import test_api  # noqa: F401  (sets up the temp database + env)
from app.database import Base, engine
from app.sync import runner
from app.sync.common import Report, SyncError


@pytest.fixture(autouse=True)
def tables():
    Base.metadata.create_all(engine)


@pytest.fixture()
def records():
    """Everything the sync logger writes while a test runs."""
    seen = []

    class Collect(logging.Handler):
        def emit(self, record):
            seen.append(record.getMessage())

    handler = Collect()
    runner.log.addHandler(handler)
    yield seen
    runner.log.removeHandler(handler)


def _fake(run):
    return types.SimpleNamespace(run=run, configured=lambda: True)


def test_a_successful_run_is_written_to_the_server_log(monkeypatch, records):
    def ok(db):
        r = Report()
        r.note("profile page: 3 songs listed directly")
        r.change("added song 'X' to 'New Releases'")
        return r
    monkeypatch.setitem(runner.SOURCES, "suno", _fake(ok))
    out = runner.run_source("suno")
    assert out["ok"]
    assert "suno ok: 1 changes" in records
    assert "suno | profile page: 3 songs listed directly" in records


def test_a_failed_run_says_why_in_the_server_log(monkeypatch, records):
    def bad(db):
        raise SyncError("no songs found on the Suno profile (layout changed?)\nprofile page: 0 songs listed directly")
    monkeypatch.setitem(runner.SOURCES, "suno", _fake(bad))
    out = runner.run_source("suno")
    assert not out["ok"]
    assert any(m.startswith("suno FAILED: no songs found") for m in records)
    assert "suno | profile page: 0 songs listed directly" in records


def test_the_sync_logger_does_not_depend_on_uvicorn_settings():
    assert runner.log.handlers and runner.log.level == logging.INFO and runner.log.propagate is False
