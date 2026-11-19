"""Loading and validating level files (levels/level_N.json).

A level file is untrusted data: it is checked completely before the game uses
it, and a bad file raises LevelError instead of being partly loaded.
"""
import json
from pathlib import Path

LEVEL_COUNT = 3
TILES = set(".#xoSG")  # empty, solid, hazard (spikes), pellet, start, goal
MIN_COLS, MAX_COLS = 20, 400
MIN_ROWS, MAX_ROWS = 10, 60
MAX_TIME_LIMIT = 3600  # seconds; no level's max_time may be longer than this


class LevelError(ValueError):
    """A level file is missing, malformed or breaks a rule."""


def is_number(value):
    """True for an int or float, but not a bool (in Python, True is an int)."""
    return type(value) in (int, float)


def pellet_ids(grid, level_number):
    """IDs of the pellets ('o' tiles) in a grid, mapped to their (col, row).

    Numbered in reading order (left to right, then top to bottom) as
    L<level>-P<nn>, so IDs are unique across levels. The engine and the server
    both use this function, so they always agree on the IDs.
    """
    spots = [(c, r) for r, line in enumerate(grid) for c, ch in enumerate(line) if ch == "o"]
    return {f"L{level_number}-P{i:02d}": spot for i, spot in enumerate(spots, start=1)}


def validate(data, expected_id):
    """Check one parsed level and return a clean copy of its known keys."""
    if not isinstance(data, dict):
        raise LevelError("level must be a JSON object")
    missing = {"id", "name", "grid", "min_time", "max_time"} - data.keys()
    if missing:
        raise LevelError(f"missing keys: {sorted(missing)}")

    level_id, name, grid = data["id"], data["name"], data["grid"]
    if type(level_id) is not int or level_id != expected_id:   # bool is not an int here
        raise LevelError(f"id must be {expected_id}")
    if not isinstance(name, str) or not 1 <= len(name) <= 32:
        raise LevelError("name must be 1-32 characters")
    if not isinstance(grid, list) or not all(isinstance(row, str) for row in grid):
        raise LevelError("grid must be a list of strings")
    if not MIN_ROWS <= len(grid) <= MAX_ROWS:
        raise LevelError(f"grid must have {MIN_ROWS}-{MAX_ROWS} rows")
    width = len(grid[0])
    if not MIN_COLS <= width <= MAX_COLS or any(len(row) != width for row in grid):
        raise LevelError(f"rows must all be the same width, {MIN_COLS}-{MAX_COLS} tiles")

    text = "".join(grid)
    unknown = set(text) - TILES
    if unknown:
        raise LevelError(f"unknown tile codes: {sorted(unknown)}")
    for ch in "SG":
        if text.count(ch) != 1:
            raise LevelError(f"level needs exactly one {ch!r} tile")

    # The server rejects a level completion faster than min_time or slower than max_time.
    min_time, max_time = data["min_time"], data["max_time"]
    if not (is_number(min_time) and is_number(max_time)
            and 0 < min_time < max_time <= MAX_TIME_LIMIT):
        raise LevelError(f"need 0 < min_time < max_time <= {MAX_TIME_LIMIT}")

    return {"id": level_id, "name": name, "grid": list(grid),
            "min_time": min_time, "max_time": max_time}


def load_levels(directory="levels"):
    """Load and validate level_1.json .. level_N.json, in order."""
    levels = []
    for n in range(1, LEVEL_COUNT + 1):
        path = Path(directory) / f"level_{n}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise LevelError(f"{path.name}: {e}") from e
        try:
            levels.append(validate(data, n))
        except LevelError as e:
            raise LevelError(f"{path.name}: {e}") from e
    return levels
