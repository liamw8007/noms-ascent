"""Server mode: the Flask API in app.py, using Flask's test client."""
import pytest

from app import create_app
from config import ConfigError, load_config

FAST_L1 = 2.1  # level 1's min_time


@pytest.fixture
def client(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "test",
                      "DATABASE": str(tmp_path / "test.db")})
    return app.test_client()


def start(client):
    assert client.post("/api/runs", json={}).status_code == 200


def finish(client, level, pellets=(), time=30.0):
    return client.post("/api/progress", json={"level": level, "pellets": list(pellets),
                                              "time": time})


# --- Configuration -----------------------------------------------------------

@pytest.mark.parametrize("value", [None, "", "change-me"])
def test_app_refuses_to_start_without_a_real_secret_key(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("SECRET_KEY", value)
    with pytest.raises(ConfigError):
        load_config()


# --- Pages and levels --------------------------------------------------------

def test_index_is_server_mode_and_engine_zip_is_served(client):
    assert b'data-mode="server"' in client.get("/").data
    res = client.get("/engine/game.zip")
    assert res.status_code == 200 and res.mimetype == "application/zip"


@pytest.mark.parametrize("n", [1, 2, 3])
def test_levels_1_to_3_are_served(client, n):
    assert client.get(f"/api/levels/{n}").get_json()["id"] == n


@pytest.mark.parametrize("path", ["/api/levels/0", "/api/levels/4", "/api/levels/-1",
                                  "/api/levels/abc", "/api/levels/..%2Fapp.py", "/game/engine.py",
                                  "/app.py", "/nope"])
def test_anything_else_is_404_json_without_details(client, path):
    res = client.get(path)
    assert res.status_code == 404
    assert res.get_json() == {"error": "Not Found"}


# --- Request rules -----------------------------------------------------------

@pytest.mark.parametrize("path", ["/api/runs", "/api/progress", "/api/scores"])
def test_post_without_json_content_type_is_415(client, path):
    res = client.post(path, data='{"name": "x"}', content_type="text/plain")
    assert res.status_code == 415


def test_body_over_4kb_is_413(client):
    start(client)
    res = client.post("/api/scores", json={"name": "x" * 5000})
    assert res.status_code == 413


@pytest.mark.parametrize("raw", ["{not json", "[1, 2]", '"text"'])
def test_body_that_is_not_a_json_object_is_400(client, raw):
    start(client)
    res = client.post("/api/progress", data=raw, content_type="application/json")
    assert res.status_code == 400


# --- Progress ----------------------------------------------------------------

def test_valid_progress_is_accepted_and_scored_by_the_server(client):
    start(client)
    res = finish(client, 1, ["L1-P01", "L1-P02"], time=FAST_L1)
    assert res.status_code == 200 and res.get_json() == {"ok": True, "score": 120}
    assert finish(client, 2).get_json()["score"] == 220


def test_progress_needs_a_run(client):
    assert finish(client, 1).status_code == 400


@pytest.mark.parametrize("body", [
    {"level": 2, "pellets": [], "time": 30},              # out of order
    {"level": True, "pellets": [], "time": 30},           # bool sent as the level
    {"level": "1", "pellets": [], "time": 30},
    {"pellets": [], "time": 30},                          # missing level
    {"level": 1, "pellets": ["L1-P99"], "time": 30},      # unknown pellet
    {"level": 1, "pellets": ["L2-P01"], "time": 30},      # pellet from another level
    {"level": 1, "pellets": ["L1-P01", "L1-P01"], "time": 30},
    {"level": 1, "pellets": [], "time": -1},
    {"level": 1, "pellets": [], "time": 1e9},
    {"level": 1, "pellets": [], "time": 1.0},             # faster than possible
    {"level": 1, "pellets": [], "time": 30, "score": 99999},  # the client can't set the score
])
def test_bad_progress_is_400(client, body):
    start(client)
    assert client.post("/api/progress", json=body).status_code == 400


def test_a_level_cannot_be_counted_twice(client):
    start(client)
    assert finish(client, 1).status_code == 200
    assert finish(client, 1).status_code == 400


def test_no_progress_after_level_3(client):
    start(client)
    for n in (1, 2, 3):
        assert finish(client, n).status_code == 200
    assert finish(client, 4).status_code == 400


def test_new_run_resets_progress(client):
    start(client)
    finish(client, 1)
    start(client)
    assert finish(client, 2).status_code == 400
    assert finish(client, 1).get_json()["score"] == 100


# --- Scores ------------------------------------------------------------------

def test_submit_and_list_scores(client):
    start(client)
    finish(client, 1, ["L1-P01"])
    res = client.post("/api/scores", json={"name": "  Nom_Fan-1 "})
    assert res.get_json() == {"ok": True, "rank": 1}
    (row,) = client.get("/api/scores").get_json()
    assert (row["name"], row["score"], row["levels_completed"]) == ("Nom_Fan-1", 110, 1)


def test_cannot_submit_before_finishing_a_level(client):
    start(client)
    assert client.post("/api/scores", json={"name": "Early"}).status_code == 400


@pytest.mark.parametrize("name", ["", "   ", "___", "<b>x</b>", "a" * 17, "Nöm", "x;DROP", 7,
                                  None, ["Nom"]])
def test_bad_names_are_rejected(client, name):
    start(client)
    finish(client, 1)
    assert client.post("/api/scores", json={"name": name}).status_code == 400


def test_client_cannot_send_its_own_score(client):
    start(client)
    finish(client, 1)
    assert client.post("/api/scores", json={"name": "Cheat", "score": 99999}).status_code == 400


def test_replayed_cookie_cannot_submit_a_run_twice(client):
    start(client)
    finish(client, 1)
    saved = client.get_cookie("session").value          # cookie saved before submitting
    assert client.post("/api/scores", json={"name": "First"}).status_code == 200
    client.set_cookie("session", saved)                 # replay it
    assert client.post("/api/scores", json={"name": "Again"}).status_code == 400
    assert len(client.get("/api/scores").get_json()) == 1


def test_top_ten_order_and_shared_ranks(client):
    for i, pellets in enumerate([[], ["L1-P01"], ["L1-P01", "L1-P02"], []] + [[]] * 8):
        start(client)
        finish(client, 1, pellets)
        res = client.post("/api/scores", json={"name": f"P{i}"})
    assert res.get_json()["rank"] == 3  # ties with the other 100-point scores
    rows = client.get("/api/scores").get_json()
    assert len(rows) == 10
    assert [r["score"] for r in rows[:3]] == [120, 110, 100]
    assert rows[2]["name"] == "P0"      # equal scores: the earlier one first
