"""Security test suite (brief Part 13), grouped by the brief's five areas.

Tests marked `open_finding` describe a finding from security/findings.md that is
not fixed yet: they are expected to fail (strict xfail), which demonstrates the
problem. Each fix removes the marker, so the same test then proves the fix.
"""
import json
import re
from pathlib import Path

import pytest
from flask import render_template

import db
from config import ConfigError, load_config
from conftest import finish, start

ROOT = Path(__file__).resolve().parent.parent
LEVEL_1 = json.loads((ROOT / "levels" / "level_1.json").read_text())


def open_finding(sec_id):
    return pytest.mark.xfail(strict=True, reason=f"{sec_id} not fixed yet")


def progress(client, body):
    return client.post("/api/progress", json=body)


# =============================================================================
# 1. Input validation: valid, missing, empty, wrong type, negative, huge, unexpected
# =============================================================================

GOOD = {"level": 1, "pellets": ["L1-P01"], "time": 30}


def test_valid_progress_is_accepted(client):
    start(client)
    client.clock.advance(30)
    assert progress(client, GOOD).get_json() == {"ok": True, "score": 110}


@pytest.mark.parametrize("missing", ["level", "pellets", "time"])
def test_progress_with_a_missing_field_is_400(client, missing):
    start(client)
    client.clock.advance(30)
    body = {k: v for k, v in GOOD.items() if k != missing}
    assert progress(client, body).status_code == 400


@pytest.mark.parametrize("raw", ["", "{}", "null", "[]", '""'])
def test_empty_bodies_are_400(client, raw):
    start(client)
    for path in ("/api/progress", "/api/scores"):
        res = client.post(path, data=raw, content_type="application/json")
        assert res.status_code == 400, (path, raw)


@pytest.mark.parametrize("field, value", [
    ("level", "1"), ("level", 1.0), ("level", True), ("level", None), ("level", [1]),
    ("pellets", "L1-P01"), ("pellets", [1]), ("pellets", None), ("pellets", {"L1-P01": 1}),
    ("time", "30"), ("time", None), ("time", True), ("time", [30]),
])
def test_progress_with_a_wrong_type_is_400(client, field, value):
    start(client)
    client.clock.advance(30)
    assert progress(client, {**GOOD, field: value}).status_code == 400


@pytest.mark.parametrize("field, value", [
    ("level", -1), ("level", 0), ("time", -1), ("time", 0), ("time", -1e308),
])
def test_progress_with_a_negative_or_zero_value_is_400(client, field, value):
    start(client)
    client.clock.advance(30)
    assert progress(client, {**GOOD, field: value}).status_code == 400


@pytest.mark.parametrize("raw", [
    '{"level": 100000000000000000000, "pellets": [], "time": 30}',
    '{"level": 1, "pellets": [], "time": 1e308}',
    '{"level": 1, "pellets": [], "time": Infinity}',   # Python's json accepts these
    '{"level": 1, "pellets": [], "time": NaN}',
    '{"level": 1, "pellets": [], "time": 1e999}',      # parses as infinity
])
def test_progress_with_a_huge_or_non_finite_value_is_400(client, raw):
    start(client)
    client.clock.advance(30)
    res = client.post("/api/progress", data=raw, content_type="application/json")
    assert res.status_code == 400


def test_a_huge_pellet_list_is_refused(client):
    start(client)
    client.clock.advance(30)
    body = {**GOOD, "pellets": [f"L1-P{i:02d}" for i in range(1000)]}
    assert progress(client, body).status_code == 413     # over the 4 KB limit


@pytest.mark.parametrize("body", [
    {**GOOD, "extra": 1},
    {**GOOD, "pellets": ["L2-P01"]},            # a pellet from another level
    {**GOOD, "pellets": ["L1-P01", "L1-P01"]},  # the same pellet twice
    {**GOOD, "pellets": ["' OR 1=1--"]},
    {**GOOD, "level": {"$gt": 0}},
])
def test_progress_with_unexpected_values_is_400(client, body):
    start(client)
    client.clock.advance(30)
    assert progress(client, body).status_code == 400


@pytest.mark.parametrize("name", [
    "", " ", "___", 123, 1.5, True, None, [], {}, "a" * 17, "<script>", "a'--", "名前",
    "No\nm", "Nom\x00",                     # (a trailing newline is trimmed, which is fine)
])
def test_bad_score_names_are_400(client, name):
    start(client)
    finish(client, 1)
    assert client.post("/api/scores", json={"name": name}).status_code == 400


@pytest.mark.parametrize("path", ["/api/levels/0", "/api/levels/4", "/api/levels/-1",
                                  "/api/levels/1.5", "/api/levels/99999999999999999999"])
def test_level_numbers_outside_1_to_3_are_404(client, path):
    assert client.get(path).status_code == 404


# =============================================================================
# 2. Game state: level progression, scores, lives, win conditions
# =============================================================================

def test_levels_cannot_be_skipped_repeated_or_extended(client):
    start(client)
    assert finish(client, 2).status_code == 400      # skip level 1
    assert finish(client, 1).status_code == 200
    assert finish(client, 1).status_code == 400      # count level 1 twice
    assert finish(client, 2).status_code == 200
    assert finish(client, 3).status_code == 200
    assert finish(client, 4).status_code == 400      # a level 4 that doesn't exist


def test_the_score_is_calculated_by_the_server(client):
    start(client)
    assert finish(client, 1, ["L1-P01", "L1-P02"]).get_json()["score"] == 120
    for key in ("score", "accepted_score", "points"):
        assert progress(client, {"level": 2, "pellets": [], "time": 30, key: 9999}).status_code == 400
    client.post("/api/scores", json={"name": "Fair"})
    assert client.get("/api/scores").get_json()[0]["score"] == 120


def test_lives_are_not_accepted_from_the_client(client):
    # Lives exist only in the browser's engine; the server never trusts or stores them.
    start(client)
    assert finish(client, 1).status_code == 200
    assert progress(client, {"level": 2, "pellets": [], "time": 30, "lives": 99}).status_code == 400


def test_a_win_cannot_be_claimed_without_finishing_a_level(client):
    start(client)
    assert client.post("/api/scores", json={"name": "Early"}).status_code == 400
    assert client.get("/api/scores").get_json() == []


def test_a_run_can_be_submitted_only_once(client):
    start(client)
    finish(client, 1)
    assert client.post("/api/scores", json={"name": "Once"}).status_code == 200
    assert client.post("/api/scores", json={"name": "Twice"}).status_code == 400
    assert finish(client, 2).status_code == 400      # no more progress after submitting


@open_finding("SEC-01")
def test_a_script_cannot_finish_a_level_faster_than_real_time(client):
    # SEC-01: a script claims every pellet at min_time, the moment the run starts.
    start(client)
    every_pellet = [f"L1-P{i:02d}" for i in range(1, 9)]
    body = {"level": 1, "pellets": every_pellet, "time": LEVEL_1["min_time"]}
    assert progress(client, body).status_code == 400          # no real time has passed
    client.clock.advance(LEVEL_1["min_time"])
    assert progress(client, body).status_code == 200          # now it's possible


@open_finding("SEC-01")
def test_the_reported_time_cannot_exceed_the_real_time(client):
    start(client)
    client.clock.advance(10)
    assert progress(client, {"level": 1, "pellets": [], "time": 60}).status_code == 400


@open_finding("SEC-01")
def test_each_level_is_timed_from_when_the_previous_one_was_accepted(client):
    start(client)
    assert finish(client, 1, time=30).status_code == 200
    assert progress(client, {"level": 2, "pellets": [], "time": 30}).status_code == 400
    client.clock.advance(30)
    assert progress(client, {"level": 2, "pellets": [], "time": 30}).status_code == 200


@open_finding("SEC-02")
def test_the_number_of_active_runs_is_capped(app, clock):
    app.config["MAX_ACTIVE_RUNS"] = 3
    clients = [app.test_client() for _ in range(4)]
    for c in clients[:3]:
        assert c.post("/api/runs", json={}).status_code == 200
    assert clients[0].post("/api/runs", json={}).status_code == 200   # replaces its own run
    res = clients[3].post("/api/runs", json={})
    assert res.status_code == 503 and res.get_json() == {"error": "Service Unavailable"}
    clock.advance(25 * 3600)                                           # all runs expire
    assert clients[3].post("/api/runs", json={}).status_code == 200


@open_finding("SEC-02")
def test_only_the_top_scores_are_kept(app, client):
    app.config["SCORES_KEPT"] = 3
    for i in range(5):
        start(client)
        finish(client, 1, ["L1-P01"] * 0 + [f"L1-P0{j}" for j in range(1, i + 1)])
        client.post("/api/scores", json={"name": f"P{i}"})
    with app.app_context():
        count = db.get_db().execute("SELECT COUNT(*) FROM scores").fetchone()[0]
    assert count == 3
    assert [r["name"] for r in client.get("/api/scores").get_json()] == ["P4", "P3", "P2"]


# =============================================================================
# 3. Error handling: no crash, no implementation details, the right status
# =============================================================================

LEAKS = re.compile(r"Traceback|File \"|\.py|Werkzeug|sqlite|line \d+|Error:", re.I)


@pytest.mark.parametrize("method, path, kwargs, status", [
    ("get", "/nope", {}, 404),
    ("get", "/api/runs", {}, 405),
    ("put", "/api/scores", {"json": {}}, 405),
    ("post", "/api/scores", {"data": "x", "content_type": "text/plain"}, 415),
    ("post", "/api/scores", {"json": {"name": "x" * 5000}}, 413),
    ("post", "/api/progress", {"data": "{bad", "content_type": "application/json"}, 400),
])
def test_errors_are_generic_json(client, method, path, kwargs, status):
    res = getattr(client, method)(path, **kwargs)
    assert res.status_code == status
    assert res.mimetype == "application/json"
    assert set(res.get_json()) == {"error"}
    assert not LEAKS.search(res.get_data(as_text=True))


def test_an_unexpected_exception_is_a_generic_500(tmp_path):
    from app import create_app
    app = create_app({"SECRET_KEY": "test", "DATABASE": str(tmp_path / "t.db")})  # TESTING off

    @app.get("/boom")
    def boom():
        return {"x": 1 / 0}

    res = app.test_client().get("/boom")
    assert res.status_code == 500
    assert res.get_json() == {"error": "Internal Server Error"}
    assert not LEAKS.search(res.get_data(as_text=True))


def test_a_broken_database_is_a_generic_500(app, tmp_path):
    app.config["TESTING"] = False
    app.config["DATABASE"] = str(tmp_path / "missing-dir" / "x.db")   # can't be opened
    res = app.test_client().get("/api/scores")
    assert res.status_code == 500
    assert not LEAKS.search(res.get_data(as_text=True))


# =============================================================================
# 4. Browser output: untrusted data is displayed safely
# =============================================================================

JS_FILES = sorted((ROOT / "static" / "js").glob("*.js"))
HTML_SINKS = re.compile(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function"
                        r"|setTimeout\(\s*['\"`]|setInterval\(\s*['\"`]")


@pytest.mark.parametrize("path", JS_FILES, ids=lambda p: p.name)
def test_javascript_has_no_html_or_code_sinks(path):
    assert not HTML_SINKS.search(path.read_text())


def test_score_names_are_inserted_as_text():
    main = (ROOT / "static" / "js" / "main.js").read_text()
    assert "td.textContent = value" in main


def test_stored_names_come_back_as_json_data_unchanged(app, client):
    # Even if a hostile name got into the database, the API returns it as JSON
    # data, never as HTML (the browser then inserts it with textContent).
    with app.app_context():
        conn = db.get_db()
        conn.execute("INSERT INTO scores (name, score, levels_completed, created_at)"
                     " VALUES (?, 1, 1, '2026-01-01')", ("<img src=x onerror=alert(1)>",))
        conn.commit()
    res = client.get("/api/scores")
    assert res.mimetype == "application/json"
    assert res.get_json()[0]["name"] == "<img src=x onerror=alert(1)>"


def test_server_mode_template_escapes_values(app):
    with app.test_request_context():
        page = render_template("index.html", mode='"><script>alert(1)</script>')
    assert "<script>alert(1)" not in page and "&lt;script&gt;" in page


@open_finding("SEC-11")
def test_static_build_template_escapes_values():
    from scripts.build_static import render_page
    page = render_page('"><script>alert(1)</script>')
    assert "<script>alert(1)" not in page and "&lt;script&gt;" in page


@open_finding("SEC-09")
def test_load_errors_are_not_shown_raw_to_the_player():
    main = (ROOT / "static" / "js" / "main.js").read_text()
    handler = main[main.rindex("main().catch"):]
    assert not re.search(r"textContent\s*=[^;\n]*\+\s*e\b", handler)


# =============================================================================
# 5. Configuration: production-oriented settings
# =============================================================================

def test_request_bodies_are_limited_to_4_kb(app):
    assert app.config["MAX_CONTENT_LENGTH"] == 4 * 1024


def test_debug_is_off_by_default(monkeypatch, tmp_path):
    from app import create_app
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    app = create_app()
    assert app.debug is False and app.testing is False


@open_finding("SEC-06")
@pytest.mark.parametrize("key", ["short", "a" * 31])
def test_weak_secret_keys_are_refused(monkeypatch, key):
    monkeypatch.setenv("SECRET_KEY", key)
    with pytest.raises(ConfigError):
        load_config()


def test_a_strong_secret_key_is_accepted(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "0123456789abcdef" * 4)
    assert load_config()["SECRET_KEY"] == "0123456789abcdef" * 4


@open_finding("SEC-04")
def test_session_cookie_flags(client):
    cookie = start(client).headers["Set-Cookie"]
    for flag in ("Secure", "HttpOnly", "SameSite=Strict", "Max-Age=86400"):
        assert flag in cookie, flag


@open_finding("SEC-05")
@pytest.mark.parametrize("path", ["/", "/api/scores", "/nope"])
def test_security_headers_are_set(client, path):
    h = client.get(path).headers
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "DENY"
    assert h["Referrer-Policy"] == "no-referrer"
    csp = h["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp and "default-src 'self'" in csp
    assert "unsafe-inline" not in csp and "'unsafe-eval'" not in csp


@open_finding("SEC-03")
def test_the_page_loads_no_third_party_code(client):
    page = client.get("/").get_data(as_text=True)
    assert not re.search(r"""(src|href)=["']?(https?:)?//""", page)
    assert 'http-equiv="Content-Security-Policy"' in page   # also protects the static build
    assert (ROOT / "static" / "pyodide" / "pyodide.asm.wasm").is_file()


@open_finding("SEC-08")
def test_cross_site_posts_are_refused(client):
    res = client.post("/api/runs", json={}, headers={"Origin": "https://evil.example"})
    assert res.status_code == 403
    assert client.post("/api/runs", json={}, headers={"Origin": "http://localhost"}).status_code == 200
    assert client.post("/api/runs", json={}).status_code == 200      # no Origin header: allowed


@open_finding("SEC-07")
def test_runtime_requirements_are_fully_pinned_with_hashes():
    text = (ROOT / "requirements.txt").read_text()
    reqs = re.findall(r"^([A-Za-z0-9_.\-\[\]]+)==\S+ \\\n((?:\s+--hash=sha256:[0-9a-f]{64}.*\n?)+)",
                      text, re.M)
    names = {name.lower() for name, _ in reqs}
    assert {"flask", "werkzeug", "jinja2", "itsdangerous", "markupsafe", "python-dotenv"} <= names
    assert "pytest" not in names                      # test tools live in requirements-dev.txt


@open_finding("SEC-10")
def test_the_build_refuses_symlinks(tmp_path, monkeypatch):
    import shutil
    from scripts import build_static, bundle_engine
    for d in ("templates", "static", "levels", "game"):
        shutil.copytree(ROOT / d, tmp_path / d, ignore=shutil.ignore_patterns("__pycache__", "pyodide"))
    (tmp_path / "secret.env").write_text("SECRET_KEY=not-for-publishing")
    (tmp_path / "static" / "leak.txt").symlink_to(tmp_path / "secret.env")
    monkeypatch.setattr(build_static, "ROOT", tmp_path)
    monkeypatch.setattr(bundle_engine, "GAME_DIR", tmp_path / "game")
    with pytest.raises(ValueError, match="symlink"):
        build_static.build(tmp_path / "out")
    (tmp_path / "static" / "leak.txt").unlink()
    (tmp_path / "game" / "leak.py").symlink_to(tmp_path / "secret.env")
    with pytest.raises(ValueError, match="symlink"):
        bundle_engine.make_zip()
