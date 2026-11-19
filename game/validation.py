"""Plausibility checks the server runs on a reported level completion.

Pure Python, like the rest of game/. The request body is untrusted: anything
the browser sends could have been typed by hand, so every field is checked
against the level file and the score is calculated here, never taken from
the client. These checks can't prove the player really played (see PRD §9).
"""
import math

from .engine import LEVEL_BONUS, PELLET_POINTS
from .level import is_number, pellet_ids


class ProgressError(ValueError):
    """The reported completion is malformed or implausible."""


def check_progress(body, level):
    """Validate {"level", "pellets", "time"} against a validated level dict.

    The caller has already checked that body["level"] is the run's next level.
    Returns the points this completion is worth.
    """
    if not isinstance(body, dict) or set(body) != {"level", "pellets", "time"}:
        raise ProgressError("expected exactly: level, pellets, time")

    pellets = body["pellets"]
    if not isinstance(pellets, list) or not all(isinstance(p, str) for p in pellets):
        raise ProgressError("pellets must be a list of strings")
    if len(set(pellets)) != len(pellets):
        raise ProgressError("duplicate pellet")
    # A pellet from another level has a different L<n> prefix, so it fails here too.
    if not set(pellets) <= pellet_ids(level["grid"], level["id"]).keys():
        raise ProgressError("unknown pellet")

    time = body["time"]
    if not is_number(time) or not math.isfinite(time):
        raise ProgressError("time must be a number")
    if not level["min_time"] <= time <= level["max_time"]:
        raise ProgressError("implausible time")

    return len(pellets) * PELLET_POINTS + LEVEL_BONUS
