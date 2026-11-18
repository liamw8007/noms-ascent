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


class LevelError(ValueError):
    """A level file is missing, malformed or breaks a rule."""


def validate(data, expected_id):
    """Check one parsed level and return a clean copy: {"id", "name", "grid"}."""
    if not isinstance(data, dict):
        raise LevelError("level must be a JSON object")
    missing = {"id", "name", "grid"} - data.keys()
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

    return {"id": level_id, "name": name, "grid": list(grid)}


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
