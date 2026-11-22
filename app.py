"""Nom's Ascent — server mode (Flask).

Start with:  flask --app app run   (after copying .env.example to .env)

The game still runs in the browser through Pyodide. The server adds:
  GET  /                  the game page
  GET  /engine/game.zip   the game/ package, zipped for Pyodide
  GET  /api/levels/<n>    level data for n = 1-3
  POST /api/runs          start a new run (sets the signed session cookie)
  POST /api/progress      report a finished level; the server checks it
  POST /api/scores        save the run's server-calculated score under a name
  GET  /api/scores        the top 10 scores

Every request body is untrusted. The session cookie holds only a random
run_id; all progress lives in the runs table (see PRD §8).
"""
import os
import re
from pathlib import Path

from flask import Flask, Response, abort, jsonify, render_template, request, session
from werkzeug.exceptions import HTTPException

import db
from config import load_config
from game.level import load_levels
from game.validation import ProgressError, check_progress
from scripts.bundle_engine import make_zip

ROOT = Path(__file__).resolve().parent
# Trimmed name: 1-16 of these characters. fullmatch() means the whole string must match.
NAME_RE = re.compile(r"[A-Za-z0-9 _-]{1,16}")

# Content Security Policy (SEC-05): only this site's own files may run or be fetched.
# 'wasm-unsafe-eval' lets Pyodide compile its WebAssembly. templates/index.html has
# the same policy in a <meta> tag for the static build, minus frame-ancestors,
# which only works as a header.
CSP = ("default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; "
       "img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
       "form-action 'self'")
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP + "; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",   # never guess a type: JSON stays JSON
    "X-Frame-Options": "DENY",             # no framing (clickjacking), for older browsers
    "Referrer-Policy": "no-referrer",
}


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(test_config if test_config is not None else load_config())
    app.config.setdefault("DATABASE", os.path.join(app.instance_path, "scores.db"))
    # A fixed rule, not a setting: request bodies over 4 KB get 413. (Not setdefault:
    # Flask's built-in config already has this key, set to None, meaning "no limit".)
    app.config["MAX_CONTENT_LENGTH"] = 4 * 1024
    # Storage limits (SEC-02). Per-IP rate limiting belongs in the reverse proxy.
    app.config.setdefault("MAX_ACTIVE_RUNS", 10_000)  # runs started in the last 24 h
    app.config.setdefault("SCORES_KEPT", 100)         # the scores table keeps only the best

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_db(app.config["DATABASE"])
    app.teardown_appcontext(db.close_db)

    # Loaded and validated once at startup; a bad level file stops the server starting.
    levels = load_levels(ROOT / "levels")
    engine_zip = make_zip()

    # --- Request checks ----------------------------------------------------------

    @app.before_request
    def require_json_posts():
        # Browsers can't send a cross-site application/json POST without a CORS
        # preflight, which this app never approves: the first defence against CSRF.
        if request.method == "POST" and request.mimetype != "application/json":
            abort(415)

    def json_body():
        """The parsed JSON body, or 400 if it isn't a JSON object."""
        body = request.get_json(silent=True)  # None for malformed JSON (still 413 if > 4 KB)
        if not isinstance(body, dict):
            abort(400)
        return body

    def current_run():
        """The session's active run, or 400 if there isn't one."""
        run = db.get_run(session.get("run_id"))
        if run is None:
            abort(400)
        return run

    @app.after_request
    def add_security_headers(response):
        response.headers.update(SECURITY_HEADERS)
        if request.is_secure:  # only meaningful over HTTPS; tells browsers to never use HTTP
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # --- Pages -------------------------------------------------------------------

    @app.get("/")
    def index():
        return render_template("index.html", mode="server")

    @app.get("/engine/game.zip")
    def engine():
        return Response(engine_zip, mimetype="application/zip")

    # --- API ---------------------------------------------------------------------

    @app.get("/api/levels/<int:n>")
    def get_level(n):
        # n picks from a fixed list, never a file path. <int:> already refuses "-1" or "../x".
        if not 1 <= n <= len(levels):
            abort(404)
        return jsonify(levels[n - 1])

    @app.post("/api/runs")
    def new_run():
        json_body()
        run_id = db.start_run(session.get("run_id"), app.config["MAX_ACTIVE_RUNS"])
        if run_id is None:
            abort(503)   # too many active runs: try again later
        session["run_id"] = run_id
        return jsonify(ok=True)

    @app.post("/api/progress")
    def progress():
        body = json_body()
        run = current_run()
        level_n = body.get("level")
        # type() is int rejects True/False, which Python otherwise treats as 1/0.
        if type(level_n) is not int or level_n != run["next_level"] or level_n > len(levels):
            abort(400)
        try:
            elapsed = db.clock() - run["level_started_at"]   # measured by the server (SEC-01)
            points = check_progress(body, levels[level_n - 1], elapsed)
        except ProgressError:
            abort(400)
        if not db.accept_progress(run["run_id"], level_n, points):
            abort(400)
        return jsonify(ok=True, score=run["accepted_score"] + points)

    @app.post("/api/scores")
    def submit_score():
        body = json_body()
        name = body.get("name")
        if not isinstance(name, str) or set(body) != {"name"}:
            abort(400)
        name = name.strip()
        if not NAME_RE.fullmatch(name) or set(name) <= {" ", "_"}:
            abort(400)
        rank = db.submit_score(current_run()["run_id"], name, app.config["SCORES_KEPT"])
        if rank is None:   # no level completed yet, or this run was already submitted
            abort(400)
        return jsonify(ok=True, rank=rank)

    @app.get("/api/scores")
    def list_scores():
        return jsonify(db.top_scores())

    # --- Errors: short generic messages, never a stack trace ----------------------

    @app.errorhandler(HTTPException)
    def http_error(e):
        return jsonify(error=e.name), e.code

    @app.errorhandler(Exception)
    def server_error(e):
        app.logger.exception("unhandled error")  # the details go to the server log only
        return jsonify(error="Internal Server Error"), 500

    return app
