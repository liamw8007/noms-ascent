"""SQLite helpers for runs and high scores.

Every query uses ? placeholders, so values from requests are never pasted into
SQL text. Each request opens its own connection (stored on flask.g) and the
app closes it when the request ends.
"""
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from flask import current_app, g

RUN_LIFETIME = timedelta(hours=24)

# Seconds since 1970. Every time in this file comes from here, so tests can
# swap in a fake clock instead of waiting in real time.
clock = time.time

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id           TEXT PRIMARY KEY,
    next_level       INTEGER NOT NULL,  -- 1-3, or 4 once level 3 is done
    accepted_score   INTEGER NOT NULL,  -- calculated by the server
    levels_completed INTEGER NOT NULL,
    submitted        INTEGER NOT NULL,  -- 1 once a score was saved for this run
    created_at       TEXT NOT NULL,
    level_started_at REAL NOT NULL      -- server clock() when next_level began (SEC-01)
);
CREATE TABLE IF NOT EXISTS scores (
    id               INTEGER PRIMARY KEY,
    name             TEXT NOT NULL,
    score            INTEGER NOT NULL,
    levels_completed INTEGER NOT NULL,
    created_at       TEXT NOT NULL
);
"""


def now(minus=timedelta()):
    """The current UTC time, minus an optional amount, as ISO-8601 text.

    The fixed format means timestamps also sort correctly as text.
    """
    return (datetime.fromtimestamp(clock(), timezone.utc) - minus).isoformat(timespec="seconds")


def init_db(path):
    conn = sqlite3.connect(path)
    try:
        # A runs table from before SEC-01 has no level_started_at column. Runs only
        # last 24 hours, so it is simply dropped and created again.
        columns = [row[1] for row in conn.execute("PRAGMA table_info(runs)")]
        if columns and "level_started_at" not in columns:
            conn.execute("DROP TABLE runs")
        conn.executescript(SCHEMA)
        # Write-ahead logging: readers don't block the single writer, so a burst of
        # requests waits briefly instead of failing with "database is locked" (SEC-02).
        conn.execute("PRAGMA journal_mode=WAL")
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

def start_run(old_run_id, max_runs):
    """Create a run and return its ID, or None if max_runs runs are already active.

    Drops the session's old run and expired runs first, so the cap counts only
    runs from the last 24 hours (SEC-02: otherwise the table could grow forever).
    """
    db = get_db()
    db.execute("DELETE FROM runs WHERE created_at < ? OR run_id = ?",
               (now(minus=RUN_LIFETIME), old_run_id))
    if db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] >= max_runs:
        db.commit()  # keep the clean-up
        return None
    run_id = secrets.token_urlsafe(16)
    db.execute("INSERT INTO runs (run_id, next_level, accepted_score, levels_completed,"
               " submitted, created_at, level_started_at) VALUES (?, 1, 0, 0, 0, ?, ?)",
               (run_id, now(), clock()))
    db.commit()
    return run_id


def get_run(run_id):
    """The run's row, or None if it doesn't exist or is older than 24 hours."""
    if not run_id:
        return None
    return get_db().execute("SELECT * FROM runs WHERE run_id = ? AND created_at >= ?",
                            (run_id, now(minus=RUN_LIFETIME))).fetchone()


def accept_progress(run_id, level, points):
    """Record a completed level. Returns False if the run moved on in the meantime.

    The WHERE clause re-checks next_level and submitted inside the UPDATE itself,
    so two requests racing each other can't both count the same level.
    """
    db = get_db()
    cur = db.execute(
        "UPDATE runs SET next_level = next_level + 1, accepted_score = accepted_score + ?,"
        " levels_completed = levels_completed + 1, level_started_at = ?"
        " WHERE run_id = ? AND next_level = ? AND submitted = 0",
        (points, clock(), run_id, level))
    db.commit()
    return cur.rowcount == 1


# --- Scores --------------------------------------------------------------------

def submit_score(run_id, name, keep):
    """Save the run's server-calculated score under name. Returns the rank, or None.

    Marking the run submitted and inserting the score happen in one transaction,
    and the UPDATE only matches an unsubmitted run, so a run is saved at most once.
    Only the best `keep` scores are stored (SEC-02), in the same order as top_scores().
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
        db.execute("DELETE FROM scores WHERE id NOT IN (SELECT id FROM scores"
                   " ORDER BY score DESC, created_at ASC, id ASC LIMIT ?)", (keep,))
    # Tied scores share a rank: 1 + the number of strictly higher scores.
    higher = db.execute("SELECT COUNT(*) FROM scores WHERE score > ?",
                        (run["accepted_score"],)).fetchone()[0]
    return higher + 1


def top_scores(limit=10):
    rows = get_db().execute(
        "SELECT name, score, levels_completed, created_at FROM scores"
        " ORDER BY score DESC, created_at ASC, id ASC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]
