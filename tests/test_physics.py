"""Checks for the platform mechanics in game/engine.py."""
import pytest

from game.engine import (DT, GRAVITY, JUMP_CUT_SPEED, JUMP_SPEED, MAX_FALL,
                         MAX_SPEED, SIZE, TILE, Game)


def make(*grids):
    """A game whose levels are the given grids, played in order."""
    return Game([{"name": f"Test {i + 1}", "grid": g} for i, g in enumerate(grids)])


# Small test levels so each test controls exactly what's around Nom.
FLAT = [
    "..........",
    "..........",
    "..........",
    "..........",
    ".S......G.",
    "##########",
]
WALL = [
    "..........",
    "..........",
    "..........",
    "....#.....",
    ".S..#...G.",
    "##########",
]
PIT = [
    "..........",
    "..........",
    "..........",
    "..........",
    ".S......G.",
    "###...####",
]
CEILING = [
    "..........",
    "..........",
    ".###......",
    "..........",
    ".S......G.",
    "##########",
]


def run(g, steps, left=False, right=False, jump=False):
    for _ in range(steps):
        g.step(left, right, jump)


def settled(grid=FLAT):
    g = make(grid)
    run(g, 30)
    assert g.on_ground
    return g


# --- Gravity -----------------------------------------------------------------

def test_gravity_accelerates_downward():
    g = make(["..", "S.", "..", "..", "..", "..", "..", "..", "G."])
    g.step(False, False, False)
    v1 = g.vy
    g.step(False, False, False)
    assert v1 == pytest.approx(GRAVITY * DT)
    assert g.vy == pytest.approx(2 * GRAVITY * DT)


def test_gravity_caps_at_terminal_velocity():
    g = make(["S."] + [".."] * 200 + ["G."])
    run(g, 120)
    assert g.vy == MAX_FALL


def test_terminal_velocity_cannot_skip_a_tile():
    assert MAX_FALL * DT < TILE


# --- Landing -----------------------------------------------------------------

def test_lands_exactly_on_floor_top():
    g = settled()
    assert g.y + SIZE == 5 * TILE
    assert g.vy == 0


def test_no_tunnelling_through_thin_floor_at_max_speed():
    grid = ["S."] + [".."] * 40 + ["##", "G."]
    g = make(grid)
    run(g, 300)
    assert g.on_ground and g.y + SIZE == 41 * TILE


# --- Jumping -----------------------------------------------------------------

def test_jump_from_ground():
    g = settled()
    g.step(False, False, True)
    assert g.vy < 0 and not g.on_ground


def test_holding_jump_only_jumps_once():
    g = settled()
    takeoffs = 0
    for _ in range(240):
        was_on_ground = g.on_ground
        g.step(False, False, True)
        if was_on_ground and g.vy < 0:
            takeoffs += 1
    assert takeoffs == 1


def test_no_jump_in_mid_air():
    g = settled()
    g.step(False, False, True)        # take off
    g.step(False, False, False)       # release
    vy = g.vy
    g.step(False, False, True)        # press again while airborne
    assert g.vy == pytest.approx(vy + GRAVITY * DT)


def test_jump_height_and_return_to_ground():
    g = settled()
    start_y = g.y
    peak = start_y
    for _ in range(120):
        g.step(False, False, True)    # held for the whole jump: full height
        peak = min(peak, g.y)
    expected = JUMP_SPEED ** 2 / (2 * GRAVITY)
    assert start_y - peak == pytest.approx(expected, rel=0.1)
    assert g.on_ground and g.y == start_y


def jump_peak(hold_frames):
    """Height Nom reaches when jump is held for hold_frames, then released."""
    g = settled()
    start_y = peak = g.y
    for i in range(120):
        g.step(False, False, i < hold_frames)
        peak = min(peak, g.y)
    assert g.on_ground and g.y == start_y
    return start_y - peak


def test_tap_jump_is_a_short_hop():
    # One frame of jump: about 10 px rising at full speed, then the cut speed's arc.
    assert jump_peak(1) < TILE
    assert jump_peak(1) >= JUMP_CUT_SPEED ** 2 / (2 * GRAVITY)


def test_longer_hold_jumps_higher():
    heights = [jump_peak(n) for n in (1, 5, 10, 20, 60)]
    assert heights == sorted(heights) and heights[0] < heights[-1]
    assert heights[-1] == pytest.approx(JUMP_SPEED ** 2 / (2 * GRAVITY), rel=0.1)


def test_release_while_falling_changes_nothing():
    g = settled()
    run(g, 30, jump=True)             # past the peak (~21 frames), now falling
    vy = g.vy
    assert vy > 0
    g.step(False, False, False)
    assert g.vy == pytest.approx(vy + GRAVITY * DT)


def test_head_bumps_ceiling():
    g = settled(CEILING)
    highest = g.y
    for _ in range(60):
        g.step(False, False, True)
        highest = min(highest, g.y)
    # The ceiling tiles span y 64..96, so Nom's top must stop at 96.
    assert highest == 3 * TILE
    assert g.on_ground


# --- Horizontal movement -----------------------------------------------------

def test_moves_right_and_left_and_faces_direction():
    g = settled()
    x = g.x
    run(g, 10, right=True)
    assert g.x > x and g.facing == 1
    x = g.x
    run(g, 30, left=True)
    assert g.x < x and g.facing == -1


def test_speed_is_capped():
    g = settled()
    run(g, 20, right=True)
    assert g.vx == MAX_SPEED


def test_friction_stops_nom_when_keys_released():
    g = settled()
    run(g, 20, right=True)
    run(g, 30)
    assert g.vx == 0


# --- Collision with walls ----------------------------------------------------

def test_wall_blocks_from_left():
    g = settled(WALL)
    run(g, 120, right=True)
    assert g.x + SIZE == 4 * TILE and g.vx == 0


def test_wall_blocks_from_right():
    g = settled(WALL)
    g.x = 6 * TILE
    run(g, 120, left=True)
    assert g.x == 5 * TILE


def test_can_jump_over_one_tile_wall():
    g = settled(WALL)
    for i in range(200):
        g.step(False, True, g.x > 2 * TILE)   # hold jump once near the wall
    assert g.status == "won"


# --- Falling -----------------------------------------------------------------

def test_walking_off_a_ledge_falls():
    g = settled(PIT)
    g.x = 3 * TILE + 2                # over the pit
    g.step(False, False, False)
    assert not g.on_ground and g.vy > 0


def test_falling_out_of_world_respawns_at_start():
    g = settled(PIT)
    start = (g.x, g.y)
    g.x = 4 * TILE
    run(g, 200)                       # fall, death animation, delay, respawn
    assert (g.x, g.y) == start and g.on_ground
    assert g.status == "playing"


# --- World boundaries --------------------------------------------------------

def test_cannot_leave_left_edge():
    g = settled()
    run(g, 120, left=True)
    assert g.x == 0


def test_cannot_leave_right_edge():
    grid = ["G.........", "S.........", "##########"]
    g = make(grid)
    run(g, 300, right=True)
    assert g.x == 10 * TILE - SIZE


# --- Goal --------------------------------------------------------------------

def test_reaching_goal_wins_and_freezes():
    g = settled()
    run(g, 200, right=True)
    assert g.status == "won"
    x = g.x
    run(g, 10, right=True)
    assert g.x == x
