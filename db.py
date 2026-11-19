"""SQLite helpers for runs and high scores.

Every query uses ? placeholders, so values from requests are never pasted into
SQL text. Each request opens its own connection (stored on flask.g) and the
app closes it when the request ends.
"""
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from flask import current_app, g

RUN_LIFETIME = timedelta(hours=24)

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id           TEXT PRIMARY KEY,
    next_level       INTEGER NOT NULL,  -- 1-3, or 4 once level 3 is done
    accepted_score   INTEGER NOT NULL,  -- calculated by the server
    levels_completed INTEGER NOT NULL,
    submitted        INTEGER NOT NULL,  -- 1 once a score was saved for this run
    created_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scores (
    id               INTEGER PRIMARY KEY,
    name             TEXT NOT NULL,
    score            INTEGER NOT NULL,
    levels_completed INTEGER NOT NULL,
    created_at       TEXT NOT NULL
);
"""


def now():
    # ISO-8601 UTC with a fixed format, so timestamps also sort correctly as text.
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db(path):
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row  # rows can be read by column name
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# --- Runs ----------------------------------------------------------------------

def start_run(old_run_id=None):
    """Create a run and return its ID. Drops the session's old run and expired runs."""
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - RUN_LIFETIME).isoformat(timespec="seconds")
    db.execute("DELETE FROM runs WHERE created_at < ? OR run_id = ?", (cutoff, old_run_id))
    run_id = secrets.token_urlsafe(16)
    db.execute("INSERT INTO runs VALUES (?, 1, 0, 0, 0, ?)", (run_id, now()))
    db.commit()
    return run_id


def get_run(run_id):
    """The run's row, or None if it doesn't exist or is older than 24 hours."""
    if not run_id:
        return None
    cutoff = (datetime.now(timezone.utc) - RUN_LIFETIME).isoformat(timespec="seconds")
    return get_db().execute(
        "SELECT * FROM runs WHERE run_id = ? AND created_at >= ?", (run_id, cutoff)).fetchone()


def accept_progress(run_id, level, points):
    """Record a completed level. Returns False if the run moved on in the meantime.

    The WHERE clause re-checks next_level and submitted inside the UPDATE itself,
    so two requests racing each other can't both count the same level.
    """
    db = get_db()
    cur = db.execute(
        "UPDATE runs SET next_level = next_level + 1, accepted_score = accepted_score + ?,"
        " levels_completed = levels_completed + 1"
        " WHERE run_id = ? AND next_level = ? AND submitted = 0",
        (points, run_id, level))
    db.commit()
    return cur.rowcount == 1


# --- Scores --------------------------------------------------------------------

def submit_score(run_id, name):
    """Save the run's server-calculated score under name. Returns the rank, or None.

    Marking the run submitted and inserting the score happen in one transaction,
    and the UPDATE only matches an unsubmitted run, so a run is saved at most once.
    """
    db = get_db()
    with db:  # commits on success, rolls back on an exception
        cur = db.execute(
            "UPDATE runs SET submitted = 1"
            " WHERE run_id = ? AND submitted = 0 AND levels_completed >= 1", (run_id,))
        if cur.rowcount != 1:
            return None
        run = db.execute("SELECT accepted_score, levels_completed FROM runs WHERE run_id = ?",
                         (run_id,)).fetchone()
        db.execute("INSERT INTO scores (name, score, levels_completed, created_at)"
                   " VALUES (?, ?, ?, ?)",
                   (name, run["accepted_score"], run["levels_completed"], now()))
    # Tied scores share a rank: 1 + the number of strictly higher scores.
    higher = db.execute("SELECT COUNT(*) FROM scores WHERE score > ?",
                        (run["accepted_score"],)).fetchone()[0]
    return higher + 1


def top_scores(limit=10):
    rows = get_db().execute(
        "SELECT name, score, levels_completed, created_at FROM scores"
        " ORDER BY score DESC, created_at ASC, id ASC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]
