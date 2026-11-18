# AI-Generated Code Analysis — *Nom's Ascent*

Part 1, §9 ("The AI Challenge"): critical evaluation of a significant piece of AI-generated code.

| | |
|---|---|
| **Project** | Nom's Ascent (CYB 318, Part 1) |
| **AI tool** | Claude Code (all engine code was generated from the prompts in `journal.md`) |
| **Code analysed** | `Game.step()` and its collision helpers in `game/engine.py` |
| **Date** | 2026-11-18 |

---

## 1. Codebase at a Glance

| File | Lines | Role |
|---|---|---|
| `game/engine.py` | 230 | The `Game` class: physics constants, movement, collision, pellets, lives, the state machine |
| `game/level.py` | 64 | Loads `levels/level_N.json` and validates them; a bad file raises `LevelError` |
| `static/js/main.js` | 199 | Loads Pyodide, reads the keyboard, runs the 60 Hz loop, draws on the canvas. Contains no game rules |
| `index.html` | 20 | Canvas and script tags (Pyodide v0.27.2 from jsDelivr) |
| `levels/*.json` | 3 files | Tile grids: `.` empty, `#` solid, `x` spikes, `o` pellet, `S` start, `G` Moon Gate |
| `tests/` | 64 tests | pytest tests for physics, levels and scoring |

The flow on every frame is: **keyboard → `main.js` → `game.step(left, right, jump)` in Python → state dict → canvas.**

## 2. Why This Code Was Chosen

`Game.step()` (`game/engine.py:140-206`) is the heart of the game. It runs 60 times a second, and almost every gameplay requirement depends on it: movement, gravity, jumping, landing, walls, world edges, hazards, pellets and reaching the goal. Collision handling is also the part of a platform game where AI-generated code most often looks correct but fails at corners and edges, so it is the code most worth questioning.

The collision part of the code, with its two helpers:

```python
# game/engine.py:122-131 — which tiles does Nom's box overlap?
def _overlapping(self):
    c0, c1 = int(self.x // TILE), int((self.x + SIZE - 0.001) // TILE)
    r0, r1 = int(self.y // TILE), int((self.y + SIZE - 0.001) // TILE)
    return [(c, r, self.grid[r][c])
            for r in range(max(r0, 0), min(r1, self.rows - 1) + 1)
            for c in range(max(c0, 0), min(c1, self.cols - 1) + 1)]

def _solid_tiles_hit(self):
    return [(c, r) for c, r, t in self._overlapping() if t == "#"]
```

```python
# game/engine.py:171-194 — inside step(): move on X, fix X, then move on Y, fix Y
new_x = self.x + self.vx * DT
self.x = max(0.0, min(new_x, self.cols * TILE - SIZE))   # world edges
if self.x != new_x:
    self.vx = 0.0
hits = self._solid_tiles_hit()
if hits:
    if self.vx > 0:
        self.x = min(c for c, _ in hits) * TILE - SIZE    # hit a wall on the right
    elif self.vx < 0:
        self.x = (max(c for c, _ in hits) + 1) * TILE     # hit a wall on the left
    self.vx = 0.0

self.y += self.vy * DT
self.on_ground = False
hits = self._solid_tiles_hit()
if hits:
    if self.vy > 0:
        self.y = min(r for _, r in hits) * TILE - SIZE    # landed on top
        self.on_ground = True
    elif self.vy < 0:
        self.y = (max(r for _, r in hits) + 1) * TILE     # bumped head
    self.vy = 0.0
```

## 3. The Eight Questions

### 3.1 What does this code do?

Each call advances the game by one fixed timestep of 1/60 s. In order, it:

1. Updates horizontal speed: it accelerates toward the held direction up to `MAX_SPEED` (240 px/s), or slows Nom with friction when no key is held.
2. Starts a jump (`vy = -640`) only on the frame the jump key goes down, and only if Nom is on the ground.
3. Cuts the jump short if the key is released while Nom is still rising faster than 240 px/s. This gives variable jump height.
4. Applies gravity, capped at a terminal velocity of 900 px/s.
5. **Moves Nom on the X axis, then resolves collisions on X.** It clamps Nom to the world edges. If Nom's box now overlaps any `#` tile, it pushes Nom back out of the side it was moving toward.
6. **Moves Nom on the Y axis, then resolves collisions on Y.** If Nom was moving down, it puts Nom's feet on top of the highest tile hit and sets `on_ground`. If Nom was moving up, it puts Nom's head under the lowest tile hit.
7. Collects any pellet Nom touches.
8. Checks for death (falling below the level, or touching the lower half of a spike tile) and then for the goal.
9. Returns a plain dictionary that the JavaScript renderer draws.

`_overlapping()` turns Nom's pixel box into a range of grid columns and rows. The `- 0.001` stops a box that merely *touches* a tile edge from counting as overlapping it. Without it, Nom standing exactly on a floor would "hit" the floor on every horizontal move.

### 3.2 Why is it necessary?

Without it, nothing in the game has physical meaning: Nom would fall through every platform, walk through walls, and never land, so jumping could never be allowed or blocked. Every one of the Part 1 required mechanics (gravity, jumping, landing, horizontal movement, collision, falling, world boundaries, hazards, reaching a goal) is carried out in this one method.

Resolving **one axis at a time** is the key design idea. If Nom moves diagonally into a corner and both axes are fixed at once, the code can't tell whether Nom hit a wall or a floor. Moving on X first and then Y means that when an overlap appears, the axis that just moved caused it, so the code knows which side to push Nom out of.

### 3.3 What inputs does it use?

| Input | Source |
|---|---|
| `left`, `right`, `jump` (booleans) | Keyboard state from `main.js` (`←`/`A`, `→`/`D`, `Space`/`↑`/`W`) |
| `self.x`, `self.y`, `self.vx`, `self.vy` | Nom's position and velocity from the previous step |
| `self.on_ground`, `self.jump_was_down` | Remembered from the previous step |
| `self.grid`, `self.rows`, `self.cols` | The current level's tile grid (validated by `level.py`) |
| Constants | `TILE`, `DT`, `GRAVITY`, `MAX_FALL`, `MOVE_ACCEL`, `FRICTION`, `MAX_SPEED`, `JUMP_SPEED`, `JUMP_CUT_SPEED`, `SIZE`, `SPIKE_TOP` |

### 3.4 What output or state does it change?

- **Changes:** `x`, `y`, `vx`, `vy`, `facing`, `on_ground`, `jump_was_down`.
- **Through helpers:** `collected` and `score` (pellets); `lives`, `status` and `death_time` (`_die()`); `score` and `status` (goal).
- **Returns:** the state dict that drives the canvas and HUD (position, status, death-animation progress, level, score, lives, remaining pellets).

### 3.5 What assumptions does it make?

1. **Nom never moves a full tile in one step.** If Nom could move 32 px or more in a step, it could pass straight through a one-tile floor (tunnelling). The code asserts `MAX_FALL * DT < TILE` (15 px < 32 px). Horizontal speed (4 px per step) and jump speed (10.7 px per step) are also well under a tile, but **only the fall speed is checked**.
2. **Nom is never already inside a wall when a step begins.** The push-out decides which way to push from the sign of the velocity. It assumes any overlap was caused by *this* step's movement.
3. **Nom is narrower and shorter than one tile** (`SIZE` 28 < `TILE` 32). This keeps the overlap to at most 2×2 tiles and lets Nom fit through one-tile gaps.
4. **There is nothing above the top of the level.** Rows above row 0 are treated as empty, and there is no ceiling clamp. Levels must leave enough headroom above their highest platform.
5. **The grid is rectangular and valid.** `level.py` checks this before `Game` ever sees the grid.
6. **The timestep is fixed.** `main.js` always calls `step()` with exactly 1/60 s worth of time. This keeps the physics deterministic and identical between the browser and pytest.
7. **Input is trusted.** Because the engine runs in the browser (Pyodide), the player can change any of this state from the developer console. This is acceptable for a single-player game, but it matters for server-side scores in Part 2.

### 3.6 What could go wrong?

I checked each of the risks below with a probe script against the real engine, in addition to the existing tests.

| Risk | What could happen | Is it real? |
|---|---|---|
| Tunnelling through a thin floor | Nom falls through a platform at high speed | **No.** The assert holds (15 px per step), and `test_no_tunnelling_through_thin_floor_at_max_speed` passes. |
| The tunnelling guard is disabled | `python -O` strips `assert` statements | **Yes, in principle.** I confirmed the engine imports under `-O` without running the check. Pyodide doesn't use `-O`, so the risk only arises if someone raises `MAX_FALL` and also runs with `-O`. |
| Corner snag when landing next to a wall | Nom catches on a wall corner instead of landing | **No.** X is resolved at the old height (still above the floor), and Y is resolved afterwards. |
| Floor counted as a wall | Nom can't walk while standing on the ground | **No.** The `- 0.001` in `_overlapping()` stops this; walking tests pass. |
| Already inside a wall | Wrong push direction or a big jump in position | **Only if the state is corrupted.** When I placed Nom inside a wall on purpose, the next step moved it 48 px to the left. Normal play can't reach this state, but editing state from the console could. |
| `on_ground` false for one frame at the top of a hop | A short hop slows to exactly `vy == 0` for one frame | **Yes, but harmless.** Nom is in the air at that moment anyway, so no jump is lost. |
| Escaping out of the top of the level | Nom jumps above row 0 and over the level | **Possible in an edited level.** In a test grid, Nom reached `y = -72.5`. The three real levels leave at least 5 empty rows above the highest platform, and the highest jump is 108 px (about 3.4 tiles), so it can't happen in the shipped levels. |
| Auto-jump after respawn | Holding jump while dying makes Nom jump the moment it respawns | **No.** Nom isn't `on_ground` on the first frame after respawn, so the held key is recorded as "already down". |

### 3.7 How was it tested?

- **Unit tests (pytest, 64 passing):** `tests/test_physics.py` checks gravity, terminal velocity, landing exactly on a floor's top edge, tunnelling at maximum speed, single jumps, no mid-air jumps, jump height, tap and hold jumps, ceiling bumps, walls on each side, jumping a one-tile wall, walking off ledges, falling out of the world, and both world edges. `tests/test_levels.py` covers spikes, including the safe upper half. `tests/test_scoring.py` covers pellets, the goal bonus and lives.
- **Edge-case probes:** a throwaway script (not part of the repo) measured the held-jump height (108.5 px, matching the documented ~108 px) and checked each risk in §3.6.
- **Manual play:** I played all three levels in the browser (journal entries 1–4).
- **Browser automation:** headless Chromium sent real key presses and read Nom's position from the canvas (described in `CLAUDE.md`). This caught a JavaScript bug that froze the first frame, which the Python tests can't see.

### 3.8 Was the AI-generated version modified? Why?

Yes. The world-edge handling (`engine.py:173-176`) changed during development, as recorded in `journal.md`:

- **Bug 1:** Nom kept moving after touching the edge of the world. The position was clamped, but `vx` was never reset, so Nom kept its speed into the edge. The fix was to remember the unclamped position and set `vx = 0` whenever the clamp moves Nom.
- **Bug 2:** the first version of that fix clamped the **old** `x` instead of the new one (`min(self.x, ...)`), so Nom couldn't move at all. Changing it to `min(new_x, ...)` fixed it.

Variable jump height (`engine.py:163-167`) was also added later at my request (journal entry 5), to make some pellets easier to reach. A second prompt asked the AI to invert some `if` conditions to make the code easier to read, which produced early returns such as the ones at the top of `step()`.

### Possible improvements (not made)

These are possible changes, not bugs in the shipped game:

- Assert the jump speed as well: `JUMP_SPEED * DT < TILE`.
- Replace the `assert` with an explicit `if ...: raise ValueError(...)` so the guard still runs under `-O`.
- Add a ceiling clamp (`y >= 0`), or make `level.py` require empty top rows, so an edited level can't let Nom escape out of the top.
- Add a pytest for the X-then-Y corner case (moving diagonally onto a ledge corner) so the main design idea has its own test.

## 4. Explaining It Without the AI

In plain language: *every 1/60 of a second, Nom moves sideways first. If that put it inside a wall, it gets pushed back out to the side it came from. Then it moves up or down. If that put it inside a tile, it gets pushed out to the top (it landed) or the bottom (it bumped its head). Because only one direction moves at a time, the code always knows which side Nom hit. Nom never moves more than half a tile per step, so it can't skip over a floor.*
