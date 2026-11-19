"""Level files, validation, spikes and moving between levels."""
import json

import pytest

from game.engine import DEATH_ANIM, DEATH_DELAY, DT, SIZE, TILE, Game
from game.level import LevelError, load_levels, validate

GOOD = {"id": 1, "name": "Test", "min_time": 1, "max_time": 60,
        "grid": ["." * 20] * 9 + [".S" + "." * 16 + "G.", "#" * 20]}


def with_grid(rows):
    return {**GOOD, "grid": rows}


def replace_row(row_index, row):
    rows = list(GOOD["grid"])
    rows[row_index] = row
    return with_grid(rows)


# --- The real level files ----------------------------------------------------

def test_all_three_level_files_load_and_validate():
    levels = load_levels("levels")
    assert [lvl["name"] for lvl in levels] == ["First Light", "Bramble Steps", "Moonlit Spire"]


def test_later_levels_contain_spikes_and_level_one_does_not():
    l1, l2, l3 = (("".join(lvl["grid"])) for lvl in load_levels("levels"))
    assert "x" not in l1
    assert "x" in l2
    assert l3.count("x") > l2.count("x")


# --- Validation --------------------------------------------------------------

def test_good_level_passes():
    assert validate(GOOD, 1)["name"] == "Test"


@pytest.mark.parametrize("bad, reason", [
    ([], "not an object"),
    ({"id": 1, "name": "Test"}, "missing grid"),
    ({**GOOD, "id": 2}, "id does not match file"),
    ({**GOOD, "id": True}, "bool is not an int"),
    ({**GOOD, "name": ""}, "empty name"),
    ({**GOOD, "name": "n" * 33}, "name too long"),
    (with_grid("...."), "grid not a list"),
    (with_grid(GOOD["grid"][:5]), "too few rows"),
    (replace_row(0, "." * 19), "ragged rows"),
    (replace_row(0, "." * 19 + "^"), "unknown tile"),
    (replace_row(0, "." * 19 + "S"), "two starts"),
    (replace_row(9, "." * 20), "no start or goal"),
    ({k: v for k, v in GOOD.items() if k != "min_time"}, "missing min_time"),
    ({**GOOD, "min_time": 0}, "min_time not positive"),
    ({**GOOD, "min_time": 60}, "min_time not below max_time"),
    ({**GOOD, "max_time": 3601}, "max_time over an hour"),
    ({**GOOD, "min_time": True}, "bool is not a number"),
    ({**GOOD, "max_time": "60"}, "string is not a number"),
])
def test_bad_levels_are_rejected(bad, reason):
    with pytest.raises(LevelError):
        validate(bad, 1)


def test_missing_or_broken_file_raises_level_error(tmp_path):
    with pytest.raises(LevelError):
        load_levels(tmp_path)
    for n in (1, 2, 3):
        (tmp_path / f"level_{n}.json").write_text(json.dumps({**GOOD, "id": n}))
    (tmp_path / "level_2.json").write_text("{not json")
    with pytest.raises(LevelError, match="level_2.json"):
        load_levels(tmp_path)


# --- Spikes ------------------------------------------------------------------

SPIKES = ["." * 10] * 3 + [".S.x....G.", "#" * 10]


def make(*grids):
    return Game([{"name": f"Test {i + 1}", "grid": g} for i, g in enumerate(grids)])


def walk_into_spikes(g):
    """Hold right until Nom touches the spikes; return Nom's start position."""
    for _ in range(30):
        g.step(False, False, False)
    start = (g.x, g.y)
    for _ in range(60):
        g.step(False, True, False)
        if g.status == "dying":
            return start
    raise AssertionError("never touched the spikes")


def test_touching_spikes_starts_death():
    g = make(SPIKES)
    walk_into_spikes(g)
    s = g.state()
    assert s["status"] == "dying" and s["death"] == 0


def test_nom_is_frozen_while_dying_and_input_is_ignored():
    g = make(SPIKES)
    walk_into_spikes(g)
    pos = (g.x, g.y)
    for _ in range(30):
        g.step(True, False, True)
    assert (g.x, g.y) == pos and g.status == "dying"


def test_death_animation_progresses_then_waits_then_respawns():
    g = make(SPIKES)
    start = walk_into_spikes(g)
    anim_steps = round(DEATH_ANIM / DT)
    delay_steps = round(DEATH_DELAY / DT)
    for _ in range(anim_steps // 2):
        g.step(False, False, False)
    assert g.state()["death"] == pytest.approx(0.5, abs=0.02)
    for _ in range(anim_steps - anim_steps // 2):
        g.step(False, False, False)
    assert g.state()["death"] == 1.0 and g.status == "dying"     # mouth closed, now the pause
    for _ in range(delay_steps - 2):
        g.step(False, False, False)
    assert g.status == "dying"
    for _ in range(3):
        g.step(False, False, False)
    assert g.status == "playing" and (g.x, g.y) == start and g.state()["death"] == 0


def test_falling_death_keeps_nom_inside_the_level_for_the_animation():
    g = make(["." * 10] * 3 + [".S......G.", "##....####"])
    g.x = 4 * TILE
    while g.status == "playing":
        g.step(False, False, False)
    assert g.status == "dying" and g.y == 5 * TILE - SIZE


def test_respawn_during_death_cancels_it():
    g = make(SPIKES)
    start = walk_into_spikes(g)
    g.press_restart()                 # what pressing R does
    assert g.status == "playing" and (g.x, g.y) == start


def test_upper_half_of_spike_tile_is_safe():
    g = make(SPIKES)
    g.x = 3 * TILE
    g.y = 3 * TILE + 16 - SIZE        # feet exactly at the spike tips
    assert not g._touching_spikes()
    g.y += 1
    assert g._touching_spikes()


def test_jumping_over_spikes_is_safe():
    g = make(SPIKES)
    for i in range(200):
        g.step(False, True, 1 <= i <= 40)   # hold jump for a full arc
    assert g.status == "won"


# --- Moving between levels ---------------------------------------------------

ONE = ["." * 10] * 3 + [".S..G.....", "#" * 10]
TWO = ["." * 12] * 3 + ["......S..G..", "#" * 12]


def walk_to_goal(g):
    for _ in range(120):
        g.step(False, True, False)


def test_goal_on_non_final_level_completes_it():
    g = make(ONE, TWO)
    walk_to_goal(g)
    assert g.status == "level_complete"


def test_next_level_loads_without_restarting():
    g = make(ONE, TWO)
    walk_to_goal(g)
    g.next_level()
    assert g.level_index == 1 and g.status == "playing"
    assert g.grid == TWO and g.x == 6 * TILE + (TILE - SIZE) / 2


def test_next_level_does_nothing_mid_level():
    g = make(ONE, TWO)
    g.next_level()
    assert g.level_index == 0


def test_goal_on_final_level_wins_and_restart_returns_to_level_one():
    g = make(ONE, TWO)
    walk_to_goal(g)
    g.next_level()
    walk_to_goal(g)
    assert g.status == "won"
    g.restart()
    assert g.level_index == 0 and g.status == "playing"


def test_state_reports_level_number_and_name():
    s = make(ONE, TWO).state()
    assert s["level"] == 1 and s["name"] == "Test 1"
