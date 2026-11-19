# CLAUDE.md — Nom's Ascent

A course project (CYB 318 Software and Application Security): a side-view platform game in which the player controls Nom, a round, open-mouthed character. The game rules are in Python, run in the browser through Pyodide. `project-prd.md` is the spec and the source of truth for requirements, milestones and the Part 2 security plan. Read it before making large changes.

## Ground rules

- **The author must be able to explain every line.** The grading rewards code the student understands over polish. Keep changes small and readable, and comment non-obvious logic, especially collision.
- **`journal.md` belongs to the user.** It's their vibe-coding journal, a graded deliverable. Never edit it unless they ask.
- **Required deliverables:** the game must be playable on GitHub Pages and must also run from a downloaded copy.
- **Keep the PRD in sync.** When a design decision changes, update `project-prd.md` to match (tile legend, statuses, file format and so on).

## Commands

```bash
pip install -r requirements.txt   # Flask, python-dotenv, pytest (pinned)
flask --app app run               # server mode → http://127.0.0.1:5000 (needs SECRET_KEY in .env, see .env.example)
python -m http.server 8000 -d docs  # static mode → http://127.0.0.1:8000 (file:// does NOT work)
pytest                            # pytest.ini sets pythonpath=. and testpaths=tests
python scripts/build_static.py    # rebuild docs/ after ANY change to templates/, static/, game/ or levels/
```

`docs/` is a committed build output, served by GitHub Pages from `main` / `/docs`. A test fails if it's stale. It includes `.nojekyll` (Jekyll drops `_`-prefixed files; harmless now that the engine ships as `engine/game.zip`, but keep it).

The first page load needs internet access, because Pyodide v0.27.2 is loaded from jsDelivr (pinned in `templates/index.html`).

## Architecture

- **`game/`: pure-Python engine.** It must never import Flask, `js` or Pyodide (NFR-06), so pytest can test it directly.
  - `engine.py`: the `Game` class, physics constants, the state machine, pellets, score and lives.
  - `level.py`: `load_levels()`, `validate()` and `pellet_ids()`. A bad level file raises `LevelError` and is never partly loaded.
  - `validation.py`: `check_progress()`, the server's plausibility check on a finished level; it returns the points (score maths lives only in the engine constants).
- **Server mode (Flask):** `app.py` (`create_app()` factory, routes, generic error handlers), `db.py` (SQLite `runs`/`scores`, `?` placeholders only), `config.py` (refuses to start without a real `SECRET_KEY`). The session cookie holds only `run_id`; all progress is in the `runs` row. The engine zip is built in memory at startup and served at `/engine/game.zip`.
- **One page, two modes:** `templates/index.html` sets `<body data-mode>`: Flask renders `server`, `build_static.py` renders `static`. Server mode loads levels from `/api/levels/<n>` and keeps the top 10 in SQLite; static mode reads `levels/*.json` and keeps scores in `localStorage` ("local scores only").
- **`static/js/main.js`: a thin JS layer only.** It loads Pyodide, unpacks `engine/game.zip` (from `scripts/bundle_engine.py`, so new `game/*.py` files are picked up automatically), copies the levels in, reads the keyboard, runs the fixed-timestep loop, draws on the canvas and runs the score table. `api.js` holds the `fetch` wrappers and the `localStorage` store.
  - **No game rules belong in JS.** Key actions call engine methods, e.g. `press_restart()` and `next_level()`.
  - Game keys are ignored while the name `<input>` has focus. Score names are inserted with `textContent`, never `innerHTML` (FR-27).
- **Fixed timestep:** 1/60 s steps through an accumulator, capped at 5 steps per frame. `step(left, right, jump)` returns a plain dict, which JS converts with `toJs` and then frees with `destroy()`.
- **Collision:** axis-aligned boxes against `#` tiles, resolved X first, then Y. The constraint `MAX_FALL * DT < TILE` (asserted at import) prevents tunnelling through floors.
- **Statuses:** `playing`, `dying` (1.0 s animation plus a 0.5 s pause), `level_complete`, `game_over` and `won`. The help overlay (`?`) is JS-only and pauses the game by not calling `step()`.
- **Rules:** 3 lives; 10 points per pellet; a 100-point bonus per Moon Gate.
  - Pellets collected in a level stay collected after a death.
  - R restarts the current level and takes away that level's pellet points, but costs no life. After a win or loss it starts a new game, and it can't cancel the final death.

## Level files (`levels/level_N.json`)

Each file has `{"id": N, "name": str, "min_time": s, "max_time": s, "grid": [str, ...]}`, with `0 < min_time < max_time ≤ 3600`; the server rejects a level completion outside that window. Rows must all be the same width (20–400 tiles), with 10–60 rows. The tile size is 32 px.

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

## Part 2 (security review) coverage

The brief's 18 sections map onto this app as follows. ✅ = real material, ⚠️ = thin, ❌ = "not applicable" only. The brief explicitly accepts documenting an attack surface as not present (§5, §8, §11), so no code change is *required*. M5 exists to give the review substance.

| Brief § | Static app (today) | Added by M5 (PRD §6.5, §7, §8) |
|---|---|---|
| 1 Baseline + diagram | ✅ Pyodide, jsDelivr, level JSON, `main.js` | Flask, routes, SQLite, `.env` |
| 2 Cursor review | ✅ | more to review |
| 3 Input validation | ⚠️ level JSON (`validate()`), keyboard | ✅ `level`, `pellets`, `time`, `name`, `/api/levels/<n>`, 4 KB limit |
| 4 XSS | ⚠️ `main.js` uses `textContent`, no `innerHTML`: a verified control | ✅ player names in the top-10 table (FR-27) |
| 5 Injection | ❌ no DB/shell; check `runPython` with level data | ✅ SQLite queries |
| 6 File/path | ⚠️ fixed `fetch(path)` list; no user filenames | ⚠️ still mostly N/A by design (no file-serving route) |
| 7 Secrets | ✅ secret scan | ✅ `SECRET_KEY`, `.env` vs `.env.example`, git history |
| 8 Sessions/cookies | ❌ no cookies | ✅ signed `run_id` cookie, `Secure`/`HttpOnly`/`SameSite`, replay |
| 9 Debug/prod config | ⚠️ `main.js` shows raw `"Failed to load: " + e` | ✅ `FLASK_DEBUG`, stack traces, error handlers (FR-28) |
| 10 Dependencies | ⚠️ pytest; Pyodide 0.27.2 from CDN | ✅ Flask, python-dotenv, Werkzeug for `pip-audit` |
| 11 Authorization/trust | ⚠️ score/lives client-only: document as a limitation | ✅ server-computed score, run state, cookie replay |
| 12 Automated tool | ⚠️ ZAP sees only headers/CSP; little for `bandit` | ✅ ZAP on endpoints, `bandit` + `pip-audit` on Flask |
| 13 Security tests | ⚠️ pytest on `validate()` with bad level files | ✅ pytest + Flask test client, every invalid-input case |
| 14–18 | docs, scale with findings | more material |

To cover every section with substance, build M5 first. See "M5: Flask server mode" below for the full change list.

**Review rules.** Build the defences the PRD already specifies. Never strip them out to create findings, and never invent findings (the brief forbids it). A control that holds under testing is documented as a verified control. Tag the M5 build (e.g. `v2-pre-review`) before any hardening; that tag, not `v1-original`, is the "before" in the before/after comparison.

**Findings already known (static app):** no SRI hash on the Pyodide script tag (PRD §9 says there should be one), no Content Security Policy, and raw error text shown to the user on load failure.

**Path chosen:** M5 first, so the review covers the server-mode column above.

## M5: Flask server mode (built; kept as the record of what it covers)

Spec: PRD §5.2, §6.5, §7, §8, §9 and §11 (API row). This list maps that spec onto the code **as it exists today**, which differs from the PRD's planned file layout (one `engine.py`, not `player.py`/`physics.py`/…). Build it in small, separately tested steps, logging each Cursor session for the journal.

**Server (new files)**
1. `app.py`: an app factory `create_app(test_config=None)` with:
   - `GET /`: serves the existing root `index.html` (keep one page for both modes);
   - `GET /api/levels/<int:n>`: `n` in {1, 2, 3}, else 404;
   - `POST /api/runs`, `POST /api/progress`, `POST /api/scores`, `GET /api/scores`: exactly as in PRD §7, including its validation column;
   - shared rules: JSON only (415 otherwise), `MAX_CONTENT_LENGTH` = 4 KB, 400 with a generic message for bad input;
   - generic 404/405/413/500 handlers, with no stack traces (FR-28).
2. `db.py`: the `runs` and `scores` tables from PRD §8, in `instance/scores.db`. Use `sqlite3` with parameterised queries only. Add a schema-init command or init on first run. Purge runs older than 24 h.
3. Config:
   - `SECRET_KEY` from the environment or `.env` (python-dotenv); refuse to start if it is missing or `change-me`;
   - debug off unless `FLASK_DEBUG=1`;
   - commit `.env.example` with placeholders only;
   - add `.env` and `instance/` to `.gitignore`.
4. Session: a signed Flask session cookie holding **only** `run_id` (`secrets.token_urlsafe(16)`). All progress lives in the `runs` row.

**Engine changes (`game/` stays free of Flask/js/Pyodide imports, NFR-06)**
5. Move pellet-ID numbering (`L<level>-P<nn>`, reading order) out of `Game._enter_level` into a pure function in `level.py`, e.g. `pellet_ids(level)`. The engine and the server must use that same function.
6. Add `min_time` / `max_time` to each `levels/level_N.json` (PRD §4.5). Make `validate()` check them (`0 < min_time < max_time ≤ 3600`) and keep them in the returned dict; today it returns only `id`, `name` and `grid`. Set `min_time` by timing a fast clean run, minus a margin.
7. Track per-level elapsed time in the engine (counted in `step()`, so it's deterministic and testable), and expose it in `state()`.
8. Put the score maths in one place, so the server computes the score from accepted progress and never takes it from the client: `PELLET_POINTS` per pellet plus `LEVEL_BONUS` per gate.

**Front end (`static/js/main.js`, `index.html`)**
9. Add a mode flag. Server mode is the default; `build_static.py` switches `docs/` to static mode. In server mode, levels come from `/api/levels/<n>`; in static mode, from `levels/*.json`.
10. Engine delivery: the PRD's plan is `scripts/bundle_engine.py` → `static/engine/game.zip` → `pyodide.unpackArchive()`. This keeps Flask from needing any route that serves `.py` files. The current code fetches `game/*.py` one by one, which Flask can't serve without a file route. Either build the bundle (preferred, matches the PRD) or record the alternative in the PRD.
11. API calls:
    - `POST /api/runs` on page load (there's no title screen yet) and when R starts a new game after `won`/`game_over`;
    - `POST /api/progress` on each `level_complete`;
    - name entry plus `POST /api/scores` on the win/game-over screen.
    - Keyboard handlers must ignore game keys while the name field has focus.
12. Top-10 table: built with `textContent` / `createElement`, **never** `innerHTML` (FR-27). Static mode uses `localStorage` and says "local scores only" (FR-30).

**Build, deps, docs, tests**
13. `requirements.txt`: add `Flask` and `python-dotenv`, pinned to the versions actually installed.
14. `build_static.py` / `docs/`: rebuild after the mode-flag change. `test_static_build.py` must still pass, and the Pages site must still work in static mode.
15. `tests/test_api.py`: Flask test client, temporary DB, test `SECRET_KEY`. Cover every case in PRD §11's API row (400s, 404, 415, HTML/long/blank names, client-set score ignored, cookie replay, `POST /api/runs` reset).
16. README and this file: add the server-mode run command (`flask --app app run` → http://127.0.0.1:5000), `.env` setup, and update "Commands", "Architecture" and "Not built yet".
17. Verify:
    - `pytest` passes;
    - a browser check plays all 3 levels in **both** modes;
    - a score submission shows up in the top 10.

    Then commit and tag `v2-pre-review`.

## Status (2026-11-19)

- **Done:** M1–M6. Movement, collision, 3 levels with transitions, spikes, death animation, pellets, score, lives, game-over and win screens, the HUD and the `?` help screen. The static build is deployed on GitHub Pages. M5 server mode is built (all 17 steps above): 141 tests pass, and a headless-Chromium run played all 3 levels in both modes (server scores matched the engine; the submitted name appeared in the top 10; R was ignored while typing the name).
- **Part 1 docs (M7):** README, design spec, journal, debugging write-ups and AI-code analysis are done. Only the final reflection is left (the user writes it).
- **Tags:** `v1-original` (annotated, commit `81e4a0d`) marks the Part 1 submission. `v2-pre-review` marks the M5 build, the "before" for Part 2. Both are local only until pushed (`git push origin <tag>`).
- **Next:**
  - the Part 1 reflection;
  - the Part 2 review (M8). See "Part 2 coverage" above.
- **Not done yet from the PRD:**
  - a title screen (the top-10 table shows below the canvas instead, FR-27);
  - a separate P/Esc pause key;
  - an SRI integrity hash on the Pyodide script tag (now a Part 2 finding; fix it in Part 2, not before).
