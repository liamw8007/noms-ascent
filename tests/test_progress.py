"""level_time, Game.progress() and the server's plausibility check (game/validation.py)."""
import pytest

from game.engine import DT, MAX_SPEED, SIZE, TILE, Game
from game.level import load_levels, pellet_ids
from game.validation import CLOCK_SLACK, ProgressError, check_progress

GRID = ["." * 20] * 9 + [".S.o.o..........G.", "#" * 20]
LEVEL = {"id": 1, "name": "Test", "grid": GRID, "min_time": 1, "max_time": 60}


def walk_to_goal(g):
    while g.status == "playing":
        g.step(False, True, False)


def test_level_time_counts_steps_and_restart_level_resets_it():
    g = Game([LEVEL])
    for _ in range(60):
        g.step(False, False, False)
    assert g.level_time == pytest.approx(60 * DT)
    g.restart_level()
    assert g.level_time == 0


def test_engine_progress_passes_the_server_check():
    # What the browser sends after a real (simulated) run is accepted.
    g = Game([LEVEL])
    walk_to_goal(g)
    p = g.progress()
    assert p["level"] == 1 and p["pellets"] == ["L1-P01", "L1-P02"]
    assert check_progress(p, LEVEL, elapsed=p["time"]) == 2 * 10 + 100


@pytest.mark.parametrize("body", [
    {"level": 1, "pellets": ["L1-P01", "L1-P01"], "time": 5},   # duplicate
    {"level": 1, "pellets": ["L1-P99"], "time": 5},             # no such pellet
    {"level": 1, "pellets": ["L2-P01"], "time": 5},             # another level's pellet
    {"level": 1, "pellets": [1], "time": 5},                    # not a string
    {"level": 1, "pellets": "L1-P01", "time": 5},               # not a list
    {"level": 1, "pellets": [], "time": 0.5},                   # faster than min_time
    {"level": 1, "pellets": [], "time": 61},                    # slower than max_time
    {"level": 1, "pellets": [], "time": float("nan")},
    {"level": 1, "pellets": [], "time": True},                  # bool is not a number
    {"level": 1, "pellets": [], "time": "5"},
    {"level": 1, "pellets": []},                                # missing time
    {"level": 1, "pellets": [], "time": 5, "score": 9999},      # extra field
])
def test_bad_progress_is_rejected(body):
    with pytest.raises(ProgressError):
        check_progress(body, LEVEL, elapsed=3600)


def test_progress_faster_than_the_server_clock_is_rejected():
    body = {"level": 1, "pellets": [], "time": 10}
    assert check_progress(body, LEVEL, elapsed=10) == 100
    assert check_progress(body, LEVEL, elapsed=10 - CLOCK_SLACK) == 100   # within the slack
    with pytest.raises(ProgressError):
        check_progress(body, LEVEL, elapsed=10 - CLOCK_SLACK - 0.1)


def test_min_time_never_rejects_a_genuine_fast_run():
    # Nom can't cover the horizontal start-to-gate distance faster than MAX_SPEED,
    # so that time is a hard lower bound for any honest run. min_time must not exceed it.
    for lvl in load_levels("levels"):
        (sc,) = [row.index("S") for row in lvl["grid"] if "S" in row]
        (gc,) = [row.index("G") for row in lvl["grid"] if "G" in row]
        distance = abs(gc - sc) * TILE - (TILE - SIZE) / 2 - SIZE
        assert lvl["min_time"] <= distance / MAX_SPEED


def test_engine_and_server_agree_on_pellet_ids():
    g = Game(load_levels("levels"))
    assert set(g.pellets) == set(pellet_ids(g.grid, 1))
