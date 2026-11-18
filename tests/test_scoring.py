"""Pellets, score, lives and the game-over / restart rules."""
from game.engine import (DEATH_ANIM, DEATH_DELAY, DT, LEVEL_BONUS, PELLET_POINTS,
                         START_LIVES, Game)
from game.level import load_levels

DEATH_STEPS = round((DEATH_ANIM + DEATH_DELAY) / DT) + 2

# Two pellets on the floor between the start and the goal.
PELLETS = ["." * 10] * 3 + [".S.o.o..G.", "#" * 10]
# Spikes right next to the start: walking right always dies.
SPIKES = ["." * 10] * 3 + [".Sx.....G.", "#" * 10]
TWO_LEVELS = [PELLETS, ["." * 10] * 3 + [".S.o....G.", "#" * 10]]


def make(*grids):
    return Game([{"name": f"Test {i + 1}", "grid": g} for i, g in enumerate(grids)])


def walk(g, steps):
    for _ in range(steps):
        g.step(False, True, False)


def die_once(g):
    walk(g, 60)
    assert g.status == "dying"
    for _ in range(DEATH_STEPS):
        g.step(False, False, False)


# --- Pellets and score -------------------------------------------------------

def test_new_game_starts_with_three_lives_and_zero_score():
    s = make(PELLETS).state()
    assert (s["lives"], s["score"]) == (START_LIVES, 0) == (3, 0)
    assert (s["pellets_got"], s["pellets_total"]) == (0, 2)


def test_pellet_ids_are_unique_across_levels():
    g = Game(load_levels("levels"))
    ids = set()
    for i in range(3):
        g.level_index = i
        g._enter_level()
        assert all(pid.startswith(f"L{i + 1}-P") for pid in g.pellets)
        ids |= set(g.pellets)
    assert len(ids) == sum("".join(lvl["grid"]).count("o") for lvl in g.levels)


def test_collecting_a_pellet_scores_once():
    g = make(PELLETS)
    walk(g, 20)
    assert g.state()["pellets_got"] >= 1
    first = g.score
    for _ in range(10):
        g.step(False, False, False)
    assert g.score == first                      # standing still doesn't re-collect
    assert g.score == PELLET_POINTS * len(g.collected)


def test_collected_pellets_are_not_drawn():
    g = make(PELLETS)
    walk(g, 20)
    assert len(g.state()["pellets"]) == 2 - len(g.collected)


def test_reaching_the_gate_adds_the_level_bonus():
    g = make(*TWO_LEVELS)
    walk(g, 120)
    assert g.status == "level_complete"
    assert g.score == 2 * PELLET_POINTS + LEVEL_BONUS


def test_score_carries_over_to_the_next_level():
    g = make(*TWO_LEVELS)
    walk(g, 120)
    g.next_level()
    assert g.score == 2 * PELLET_POINTS + LEVEL_BONUS and g.state()["pellets_got"] == 0


# --- Lives and losing --------------------------------------------------------

def test_dying_costs_one_life_and_keeps_pellets():
    g = make(["." * 10] * 3 + [".Sox....G.", "#" * 10])
    die_once(g)
    assert g.lives == 2 and g.status == "playing"
    assert g.score == PELLET_POINTS and len(g.collected) == 1


def test_losing_the_last_life_is_game_over():
    g = make(SPIKES)
    die_once(g)
    die_once(g)
    walk(g, 60)
    assert g.lives == 0 and g.status == "dying"
    for _ in range(DEATH_STEPS):
        g.step(False, False, False)
    assert g.status == "game_over"


def test_game_over_ignores_movement_and_r_starts_a_new_game():
    g = make(SPIKES)
    for _ in range(3):
        die_once(g)
    assert g.status == "game_over"
    g.step(False, True, True)
    assert g.status == "game_over"
    g.press_restart()
    assert (g.status, g.lives, g.score, g.level_index) == ("playing", 3, 0, 0)


def test_r_cannot_cancel_the_final_death():
    g = make(SPIKES)
    die_once(g)
    die_once(g)
    walk(g, 60)                                  # third death starts, 0 lives left
    g.press_restart()
    assert g.status == "dying"


# --- Restarting a level ------------------------------------------------------

def test_r_restarts_the_level_and_removes_its_pellet_points():
    g = make(*TWO_LEVELS)
    walk(g, 120)
    g.next_level()
    banked = g.score
    walk(g, 20)
    assert g.score > banked
    g.press_restart()
    assert g.score == banked and not g.collected and g.level_index == 1
    assert g.lives == 3                          # restarting is not a death


def test_win_then_r_starts_a_new_game():
    g = make(PELLETS)
    walk(g, 120)
    assert g.status == "won"
    g.press_restart()
    assert (g.status, g.score, g.lives) == ("playing", 0, 3)
