"""Nom's Ascent — game engine.

Pure Python: no Flask, js or Pyodide imports, so it runs the same in the
browser (Pyodide) and under plain pytest. Levels come from game/level.py.
"""
from .level import pellet_ids

TILE = 32
DT = 1 / 60            # fixed timestep, seconds
GRAVITY = 1800         # px/s^2
MAX_FALL = 900         # terminal velocity, px/s
MOVE_ACCEL = 1800      # px/s^2 while a direction key is held
FRICTION = 1600        # px/s^2 when no direction key is held
MAX_SPEED = 240        # px/s
JUMP_SPEED = 640       # px/s upward impulse (~3.5 tiles high if jump is held)
JUMP_CUT_SPEED = 240   # releasing jump early caps upward speed at this (short hop)
SIZE = 28              # Nom's bounding box, px
SPIKE_TOP = TILE // 2  # spikes fill the lower half of an 'x' tile
DEATH_ANIM = 1.0       # seconds for the death animation (mouth opens until it closes up)
DEATH_DELAY = 0.5      # pause after the animation before respawning
START_LIVES = 3
PELLET_POINTS = 10
LEVEL_BONUS = 100      # awarded for reaching the Moon Gate
PELLET_HIT = 14        # width of the square at a pellet's centre that Nom must touch

# Nom must never move a whole tile in one step, or it could pass through a floor.
assert MAX_FALL * DT < TILE


class Game:
    """levels: list of {"name": str, "grid": [str, ...]}, played in order."""

    def __init__(self, levels):
        self.levels = levels
        self.restart()

    # --- Level flow ----------------------------------------------------------

    def restart(self):
        """Start the whole game again: level 1, full lives, score 0."""
        self.level_index = 0
        self.lives = START_LIVES
        self.score = 0
        self._enter_level()

    def next_level(self):
        """From the level-complete screen, move on without reloading anything."""
        if self.status != "level_complete":
            return
        self.level_index += 1
        self._enter_level()

    def restart_level(self):
        """Replay the current level from scratch: its pellets and their points are reset."""
        self.score = self.level_start_score
        self.collected = set()
        self.level_time = 0.0
        self.respawn()

    def press_restart(self):
        """What the R key does, which depends on the current screen."""
        if self.status in ("game_over", "won"):
            self.restart()
        elif self.status in ("playing", "dying") and self.lives > 0:
            self.restart_level()

    def _enter_level(self):
        self.grid = self.levels[self.level_index]["grid"]
        self.rows, self.cols = len(self.grid), len(self.grid[0])
        self.start = self._find("S")
        # Pellets are 'o' tiles with IDs like L2-P01 (see level.pellet_ids).
        self.pellets = pellet_ids(self.grid, self.level_index + 1)
        self.level_start_score = self.score
        self.collected = set()
        self.level_time = 0.0   # seconds in this level, deaths included; sent to the server
        self.respawn()

    def respawn(self):
        """Put Nom back at the current level's start."""
        col, row = self.start
        self.x = col * TILE + (TILE - SIZE) / 2
        self.y = (row + 1) * TILE - SIZE      # feet on the bottom of the S tile
        self.vx = self.vy = 0.0
        self.on_ground = False
        self.facing = 1
        self.jump_was_down = False
        self.death_time = 0.0
        self.status = "playing"

    def _die(self):
        """Lose a life, freeze Nom and start the death animation.

        step() respawns Nom afterwards, or ends the game if no lives are left.
        Pellets collected in this level stay collected.
        """
        self.lives -= 1
        self.status = "dying"
        self.death_time = 0.0
        self.vx = self.vy = 0.0
        # After a fall, keep Nom at the bottom edge of the level so the animation is visible.
        self.y = min(self.y, self.rows * TILE - SIZE)

    def _advance_death(self):
        """One step of the death animation; respawn or end the game when it is over."""
        self.death_time += DT
        if self.death_time < DEATH_ANIM + DEATH_DELAY:
            return                      # still animating or pausing
        if self.lives > 0:
            self.respawn()
        else:
            self.status = "game_over"

    def _find(self, ch):
        for row, line in enumerate(self.grid):
            if ch in line:
                return line.index(ch), row
        raise ValueError(f"level has no {ch!r} tile")

    # --- Tile queries --------------------------------------------------------

    def _overlapping(self):
        """(col, row, tile) for every grid tile Nom's box overlaps."""
        c0, c1 = int(self.x // TILE), int((self.x + SIZE - 0.001) // TILE)
        r0, r1 = int(self.y // TILE), int((self.y + SIZE - 0.001) // TILE)
        return [(c, r, self.grid[r][c])
                for r in range(max(r0, 0), min(r1, self.rows - 1) + 1)
                for c in range(max(c0, 0), min(c1, self.cols - 1) + 1)]

    def _solid_tiles_hit(self):
        return [(c, r) for c, r, t in self._overlapping() if t == "#"]

    def _touching_spikes(self):
        # Only the lower half of a spike tile hurts, matching how it is drawn.
        return any(t == "x" and self.y + SIZE > r * TILE + SPIKE_TOP
                   for _, r, t in self._overlapping())

    # --- Simulation ----------------------------------------------------------

    def step(self, left, right, jump):
        """Advance one fixed timestep. Returns the state the renderer needs."""
        if self.status in ("playing", "dying"):
            self.level_time += DT
        if self.status == "dying":
            self._advance_death()
            return self.state()
        if self.status != "playing":
            return self.state()

        # Horizontal: accelerate toward the held direction, else apply friction.
        direction = (1 if right else 0) - (1 if left else 0)
        if direction:
            self.vx += direction * MOVE_ACCEL * DT
            self.vx = max(-MAX_SPEED, min(MAX_SPEED, self.vx))
            self.facing = direction
        else:
            slow = FRICTION * DT
            self.vx = 0.0 if abs(self.vx) <= slow else self.vx - slow * (1 if self.vx > 0 else -1)

        # Jump only on the press itself (not while held) and only from the ground.
        if jump and not self.jump_was_down and self.on_ground:
            self.vy = -JUMP_SPEED
        self.jump_was_down = jump

        # Variable jump height: if jump is released while Nom is still rising
        # fast, cut the upward speed down. Holding jump gives the full arc; a
        # quick tap gives a short hop (about 1 tile).
        if not jump and self.vy < -JUMP_CUT_SPEED:
            self.vy = -JUMP_CUT_SPEED

        self.vy = min(self.vy + GRAVITY * DT, MAX_FALL)

        # Collision is resolved one axis at a time: X first, then Y. Moving on
        # one axis then pushing out tells us exactly which side Nom hit.
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

        self._collect_pellets()

        # Falling out of the world or touching spikes costs a life.
        if self.y > self.rows * TILE or self._touching_spikes():
            self._die()
        elif any(t == "G" for _, _, t in self._overlapping()):
            self.score += LEVEL_BONUS
            last = self.level_index == len(self.levels) - 1
            self.status = "won" if last else "level_complete"

        return self.state()

    def _collect_pellets(self):
        """Pick up any pellet whose centre square (PELLET_HIT px wide) Nom overlaps."""
        half = PELLET_HIT / 2
        for pid, (c, r) in self.pellets.items():
            if pid in self.collected:
                continue
            px, py = c * TILE + TILE / 2, r * TILE + TILE / 2
            if (self.x < px + half and self.x + SIZE > px - half and
                    self.y < py + half and self.y + SIZE > py - half):
                self.collected.add(pid)
                self.score += PELLET_POINTS

    def progress(self):
        """What server mode reports when a level is finished (POST /api/progress)."""
        return {"level": self.level_index + 1, "pellets": sorted(self.collected),
                "time": round(self.level_time, 3)}

    def state(self):
        return {"x": self.x, "y": self.y, "size": SIZE, "facing": self.facing,
                "moving": abs(self.vx) > 1, "status": self.status,
                "death": min(self.death_time / DEATH_ANIM, 1.0),  # 0..1 animation progress
                "level": self.level_index + 1, "levels": len(self.levels),
                "name": self.levels[self.level_index]["name"],
                "score": self.score, "lives": self.lives,
                "pellets_total": len(self.pellets), "pellets_got": len(self.collected),
                # Tile positions of pellets still to collect, for drawing.
                "pellets": [list(pos) for pid, pos in self.pellets.items()
                            if pid not in self.collected]}
