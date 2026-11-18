# CLAUDE.md — Nom's Ascent

A course project (CYB 318 Software and Application Security): a side-view platform game in which the player controls Nom, a round, open-mouthed character. The game rules are in Python, run in the browser through Pyodide. `project-prd.md` is the spec and the source of truth for requirements, milestones and the Part 2 security plan. Read it before making large changes.

## Ground rules

- **The author must be able to explain every line.** The grading rewards code the student understands over polish. Keep changes small and readable, and comment non-obvious logic, especially collision.
- **`journal.md` belongs to the user.** It's their vibe-coding journal, a graded deliverable. Never edit it unless they ask.
- **Required deliverables:** the game must be playable on GitHub Pages and must also run from a downloaded copy.
- **Keep the PRD in sync.** When a design decision changes, update `project-prd.md` to match (tile legend, statuses, file format and so on).

## Commands

```bash
python -m http.server 8000      # then open http://127.0.0.1:8000 (opening index.html as file:// does NOT work)
pip install -r requirements.txt # only pytest for now
pytest                          # pytest.ini sets pythonpath=. and testpaths=tests
python scripts/build_static.py  # rebuild docs/ (the GitHub Pages site) after ANY change to index.html, static/, game/ or levels/
```

`docs/` is a committed build output, served by GitHub Pages from `main` / `/docs`. A test fails if it's stale. It includes `.nojekyll`, which is required: without it Pages' Jekyll drops `game/__init__.py`.

The first page load needs internet access, because Pyodide v0.27.2 is loaded from jsDelivr (pinned in `index.html`).

## Architecture

- **`game/`: pure-Python engine.** It must never import Flask, `js` or Pyodide (NFR-06), so pytest can test it directly.
  - `engine.py`: the `Game` class, physics constants, the state machine, pellets, score and lives.
  - `level.py`: `load_levels()` and `validate()`. A bad level file raises `LevelError` and is never partly loaded.
- **`static/js/main.js`: a thin JS layer only.** It loads Pyodide, copies `game/*.py` and `levels/*.json` into Pyodide's filesystem, reads the keyboard, runs the fixed-timestep loop and draws on the canvas.
  - **No game rules belong in JS.** Key actions call engine methods, e.g. `press_restart()` and `next_level()`.
  - A new engine file must also be added to `ENGINE_FILES` in `main.js`, or the browser won't load it.
- **Fixed timestep:** 1/60 s steps through an accumulator, capped at 5 steps per frame. `step(left, right, jump)` returns a plain dict, which JS converts with `toJs` and then frees with `destroy()`.
- **Collision:** axis-aligned boxes against `#` tiles, resolved X first, then Y. The constraint `MAX_FALL * DT < TILE` (asserted at import) prevents tunnelling through floors.
- **Statuses:** `playing`, `dying` (1.0 s animation plus a 0.5 s pause), `level_complete`, `game_over` and `won`. The help overlay (`?`) is JS-only and pauses the game by not calling `step()`.
- **Rules:** 3 lives; 10 points per pellet; a 100-point bonus per Moon Gate.
  - Pellets collected in a level stay collected after a death.
  - R restarts the current level and takes away that level's pellet points, but costs no life. After a win or loss it starts a new game, and it can't cancel the final death.
- **Not built yet:** `templates/` is empty, reserved for Flask server mode (M5). There's no `app.py` or database yet.

## Level files (`levels/level_N.json`)

Each file has `{"id": N, "name": str, "grid": [str, ...]}`. Rows must all be the same width (20–400 tiles), with 10–60 rows. The tile size is 32 px.

| Char | Meaning |
|---|---|
| `.` | empty |
| `#` | solid |
| `x` | spikes; only the lower half of the tile hurts |
| `o` | pellet; IDs are `L<level>-P<nn>`, numbered in reading order |
| `S` | start (exactly one) |
| `G` | Moon Gate (exactly one) |

Physics limits for level design:
- Jump height is variable: holding jump reaches about 108 px (about 3.5 tiles); releasing early caps upward speed at `JUMP_CUT_SPEED`, so a tap is about 24 px. Design levels for a full hold.
- Horizontal jump reach is about 5 tiles.
- A row of spikes on flat ground must be at most 3 tiles wide to be jumpable.

## Verifying changes

- **Run `pytest`.** Tests build tiny grids of their own, via a `make(*grids)` helper, so each test controls Nom's surroundings.
- **After changing levels or physics, check every level can still be completed and every pellet reached.** The solver used so far was a throwaway breadth-first-search script in the scratchpad, not part of the repo. It works by snapshotting and restoring `Game` attributes and trying move/jump actions for 4 frames each.
- **Browser check:** headless Chromium (`/usr/bin/chromium --headless=new --remote-debugging-port=…`) driven over CDP from Node, sending real key events. Nom's position is found by scanning the canvas for its colour `#2ec4b6`.
  - Run this after any `main.js` change, since the tests don't cover JS.
  - A JS bug once froze the first frame; only the browser check caught it.

## Status (2026-11-17)

- **Done:** M1–M4. Movement, collision, 3 levels with transitions, spikes, death animation, pellets, score, lives, game-over and win screens, the HUD and the `?` help screen.
- **M6 in progress:** `scripts/build_static.py` builds `docs/`, verified in headless Chromium under a `/noms-ascent/` subpath. Still needed: enable Pages in the repo settings and confirm the live URL.
- **Next:**
  - the README and Part 1 documentation (M7);
  - Flask server mode (M5), which feeds the Part 2 security review.
- **Not done yet from the PRD:**
  - a title screen;
  - a separate P/Esc pause key;
  - the `game.zip` engine bundle (JS fetches the `.py` files directly for now);
  - an SRI integrity hash on the Pyodide script tag.
