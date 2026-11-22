"""Shared fixtures for the server-mode tests (test_api.py, test_security.py)."""
import pytest

import db
from app import create_app


class FakeClock:
    """Stands in for db.clock, so tests decide how much real time has passed."""

    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(db, "clock", fake, raising=False)
    return fake


@pytest.fixture
def app(tmp_path, clock):
    return create_app({"TESTING": True, "SECRET_KEY": "test",
                       "DATABASE": str(tmp_path / "test.db")})


@pytest.fixture
def client(app, clock):
    c = app.test_client()
    c.clock = clock
    return c


def start(client):
    res = client.post("/api/runs", json={})
    assert res.status_code == 200
    return res


def finish(client, level, pellets=(), time=30.0):
    """Report a finished level, as if the player really took `time` seconds."""
    client.clock.advance(time)
    return client.post("/api/progress", json={"level": level, "pellets": list(pellets),
                                              "time": time})
