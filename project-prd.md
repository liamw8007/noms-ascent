# Program Requirements Document — *Nom's Ascent*

| | |
|---|---|
| **Course** | CYB 318 Software and Application Security — Assumption University |
| **Author** | Liam Waldron |
| **Date** | 2026-11-17 |
| **Status** | Draft v2 (revised against the Part 1 assignment brief) |
| **Covers** | Part 1 — Vibe Coding a Web-Based Platform Game · Part 2 — Security Review and Hardening |
| **Tools** | Python, Cursor (AI-assisted), HTML/CSS/JavaScript, Flask, Pyodide |

---

## 1. Purpose

Build an original, keyboard-controlled, side-view platform game in which the player controls a round, open-mouthed arcade-style character through three increasingly difficult levels. The assignment brief requires a Pac-Man-style character; Nom is an original, canvas-drawn take on that brief, not a copy of existing artwork. Python must be a significant part of the implementation. The game must be playable in a browser by someone who has never seen the source code, and it must work in two ways, both required by the brief:

- **Published** on the author's GitHub Pages site.
- **Downloaded** from the repo, run locally and opened in a browser.

GitHub Pages only serves static files and cannot run Flask. Pyodide (Python compiled to WebAssembly) is therefore what keeps Python "a significant part of the implementation" in the published build.

The project is also the target of a later security review (Part 2), so the PRD defines the architecture, trust boundaries and data flows up front, and sets out the hardening work as a separate phase.

The project's learning goal matters more than polish: every major component must be something the author can explain without Cursor. This PRD is the first step of the vibe-coding process, as *The Comprehensive Guide to Vibe Coding (TheAIHorizon.org)* recommends.

## 2. Goals and Non-Goals

### Goals
- G1. A complete, playable game with three distinct levels, win/lose conditions and a restart option.
- G2. Python owns the game rules: physics, collision, level loading and game state.
- G3. Two ways to run it:
  - **Server mode:** a Flask app that also stores high scores in SQLite and validates progress.
  - **Static mode (required deliverable):** a GitHub Pages build where the same Python code runs in the browser through Pyodide. The same build can also be served locally.
- G4. A documented, iterative vibe-coding process: a design spec, a journal of at least 5 sessions, at least 3 debugging write-ups, an analysis of one piece of AI-generated code, and a reflection (templates in §14).
- G5. A codebase small and clear enough to undergo a meaningful security review in Part 2.

### Scope priority
The brief's grading notes say a simpler game the student understands well beats an impressive one built from AI output the student hasn't examined. Part 1 is complete without server mode: M1–M4, M6 and M7 are the Part 1 core. Server mode (M5) is built after them, mainly to give the Part 2 security review a real attack surface. If time runs short, M5 slips, not the core.

### Non-Goals
- User accounts, passwords or login.
- Multiplayer or real-time networking.
- Mobile or touch controls (keyboard only).
- Copying any existing game's characters, art, music, names or level layouts.
- A production-grade anti-cheat system. The server validates plausibility only, and the limits of that are documented (see §9).

## 3. Users

| User | Need |
|---|---|
| **Player** (another student) | Open the Pages URL, or download the repo and run one command, read the on-screen instructions, and play. |
| **Instructor / grader** | Clone the repo, follow the README, run the tests, review the docs, and ask the author to explain the code. |
| **Security reviewer** (author, in Part 2) | A clear map of the endpoints, inputs, stored data and dependencies. |

## 4. Game Design Specification (one-page spec)

### 4.1 Concept
- **Name:** *Nom's Ascent*
- **Player character:** **Nom**, a teal, circular creature with a wedge-shaped mouth that opens and closes as it moves. Nom is drawn on the canvas with vector shapes; no sprite files are copied from anywhere.
- **Setting:** the Glow Gardens, a night-time garden of floating stone ledges, bramble spikes and firefly pellets.
- **Objective:** guide Nom from the left side of each level to the **Moon Gate** on the far right, collecting firefly pellets along the way, without running out of lives.
- **Win:** pass through the Moon Gate in Level 3.
- **Lose:** lose all 3 lives. A life is lost when Nom touches a hazard or falls off the bottom of the world.

### 4.2 Controls

| Key | Action |
|---|---|
| ← / A | Move left |
| → / D | Move right |
| Space / ↑ / W | Jump (only while standing on something); hold for a higher jump, tap for a short hop |
| P / Esc | Pause or resume |
| R | During play: restart the current level. From the game-over or win screen: restart the whole game as a new run (see FR-17). |
| Enter | Start the game, or continue from a message screen |

### 4.3 Levels

Each level is a tile grid stored as data (`levels/level_N.json`), not as code. The file format is defined in §4.5.

| Level | Name | New challenge | Content |
|---|---|---|---|
| 1 | **First Light** | Movement, jumping, reaching the goal | Flat ground, a few low ledges, one small gap, pellets placed to teach jumping, Moon Gate at the end. No hazards. |
| 2 | **Bramble Steps** | Gaps, raised platforms, still hazards | Wider gaps, staircase ledges, bramble spikes on the ground and on ledges, an optional higher route with more pellets. |
| 3 | **Moonlit Spire** | Combined hazards and precise jumps | Vertical climbing sections, narrow ledges over spike pits, longer jump sequences, and a final run to the Moon Gate. |

When a level is finished, the game moves straight to the next one with a short "Level Complete" screen. The app is never reloaded between levels.

### 4.4 Game State

| Field | Type | Notes |
|---|---|---|
| `player.x`, `player.y` | float | World position in pixels |
| `player.vx`, `player.vy` | float | Velocity |
| `player.on_ground` | bool | Controls whether a jump is allowed |
| `player.facing` | `-1` or `1` | Which way the sprite faces |
| `level_index` | int, 0–2 | The current level. **Indexing convention:** the engine counts from 0, while level files, the HUD and the API count from 1 (`level_N.json`, `/api/levels/<n>`). The conversion `n = level_index + 1` happens in one helper only, in `game/level.py`. |
| `lives` | int, 0–3 | Starts at 3 |
| `score` | int ≥ 0 | +10 per pellet, plus a bonus for finishing a level |
| `collected` | set of pellet IDs | Collected pellets in the current level |
| `status` | enum | `title`, `playing`, `paused`, `level_complete`, `dying` (1 s death animation + 0.5 s pause, then respawn), `game_over`, `won` |
| `level_time` | float | Seconds spent in the current level, used for validating scores |

### 4.5 Level File Format

```json
{
  "id": 2,
  "name": "Bramble Steps",
  "grid": [
    "..............................",
    "........oo.......ooo..........",
    "S.......xx......#####.o......G",
    "##############..##############"
  ]
}
```

| Key | Rule |
|---|---|
| `id` | int, 1–3, must match the file name |
| `name` | string, 1–32 characters |
| `grid` | List of equal-length strings. Width 20–400 tiles, height 10–60 tiles. |
| `min_time`, `max_time` | *Added in M5.* Seconds. `0 < min_time < max_time ≤ 3600`. Used by the server's plausibility check (§7). `min_time` is set by timing a fast clean run and subtracting a margin. |

The tile size is fixed at 32 px in `game/engine.py`, not set per file.

**Pellet IDs** are not stored in the file. The engine numbers the `o` tiles in reading order (left to right, then top to bottom) as `L<level>-P<nn>`, e.g. `L2-P01`. IDs are therefore unique **across** levels, and the server can derive the same IDs from the same file.

**Tile legend:**

| Char | Meaning |
|---|---|
| `.` | Empty |
| `#` | Solid stone ledge |
| `x` | Bramble spikes (hazard). Only the lower half of the tile hurts, matching how the spikes are drawn. |
| `o` | Firefly pellet (10 points). Collected when Nom touches the 14 px square at the tile's centre. |
| `S` | Player start (exactly one) |
| `G` | Moon Gate goal (exactly one) |

Any other character, a missing key or a broken rule makes the whole file invalid (FR-13).

## 5. Architecture

### 5.1 Overview

```
Browser
  │  keyboard events
  ▼
static/js/main.js  ── requestAnimationFrame loop ──► canvas drawing (also in main.js)
  │  calls step(inputs) at a fixed 1/60 s (accumulator)
  ▼
Pyodide (Python in WebAssembly)
  │  unpacks engine/game.zip, then imports the shared  game/  package
  ▼
game/ engine (physics, collision, levels, state)  ◄── same code imported by Flask
  │
  │  (server mode only) fetch() JSON
  ▼
Flask app (app.py)
  ├── /api/levels/<n>     level data
  ├── /api/runs           start a new run
  ├── /api/progress       records level completion (validated)
  ├── /api/scores         submit and list high scores
  └── SQLite (instance/scores.db: runs, scores)
```

- **Shared engine.** The `game/` package is plain Python with no Flask or browser imports. The Flask server imports it to validate level completions and scores. Pyodide loads the same files into the browser to run the real-time loop. This keeps all the rules in Python while still allowing smooth 60 FPS gameplay.
- **JavaScript stays thin.** It handles keyboard input, the `requestAnimationFrame` timing, canvas drawing, HUD updates and `fetch` calls. It does not contain game rules.
- **Fixed timestep.** The engine advances in fixed 1/60 s steps. This keeps physics deterministic and makes it testable with pytest. `main.js` uses an accumulator:
  - Each animation frame adds the real elapsed time.
  - It then runs as many 1/60 s `step()` calls as fit, capped at 5 per frame so a long pause can't trigger a burst of catch-up steps.
  - It keeps the remainder for the next frame.

  This keeps game speed the same on 60, 120 and 144 Hz displays.
- **How Pyodide gets the engine.** `scripts/bundle_engine.py` zips `game/*.py` (`make_zip()`). Flask builds the zip in memory at startup and serves those fixed bytes at `GET /engine/game.zip`; `build_static.py` writes the same bytes to `docs/engine/game.zip`. No zip is kept in `static/`. In both modes, `main.js` fetches that zip and unpacks it into Pyodide's virtual filesystem with `pyodide.unpackArchive()`, then runs `import game`. Using one mechanism for both modes means Flask needs no route that serves source files, and a route serving files by path would be attack surface.
- **Data across the boundary.** Each frame, `step()` returns one small plain dict: player position and facing, status, score, lives and pellets collected. JS only converts that dict. This keeps the per-frame cost of crossing the Python/JS boundary low (NFR-01).

### 5.2 Run Modes

| | Server mode | Static mode (GitHub Pages) |
|---|---|---|
| Start | `flask --app app run` → http://127.0.0.1:5000 | Open the Pages URL, or locally: `python -m http.server 8000 -d docs` → http://127.0.0.1:8000 |
| Python runs in | Browser (Pyodide) + Flask server | Browser only (Pyodide) |
| Level data | `GET /api/levels/<n>` | Bundled JSON files |
| High scores | SQLite through `/api/scores` | `localStorage` (this device only) |
| Progress validation | Server-side | None (documented limitation) |

A build script (`scripts/build_static.py`) does these things:
- renders `templates/index.html` with Jinja2 in static mode (`<body data-mode="static">`; Flask renders the same template with `mode="server"`);
- copies `static/` and `levels/*.json` into a fresh `docs/`, and writes the engine zip to `docs/engine/game.zip`;
- writes an empty `docs/.nojekyll`. GitHub Pages runs Jekyll by default, and Jekyll drops files whose names start with `_`. Nothing in the build needs such a file now that the engine is zipped, but the file keeps Jekyll from ever surprising us.

`docs/` is committed. `tests/test_static_build.py` fails if it is out of date with the sources, so rebuild before every push. GitHub Pages serves the site from `docs/` on the main branch (Settings → Pages → Deploy from a branch → `main` / `/docs`).

**Opening the files directly doesn't work.** Opening `docs/index.html` as a `file://` page fails, because browsers block `fetch()` and WebAssembly loading from `file://`. The README must therefore give the one-line `http.server` command for anyone who downloads the static build. Both modes need an internet connection the first time they load, to fetch Pyodide from the CDN (§15, Q3).

### 5.3 Project Structure

The engine stayed in one `engine.py` rather than the `player.py`/`physics.py`/… split first planned, and the drawing code stayed in `main.js`.

```
noms-ascent/
├── app.py                  # Flask app factory, routes, error handlers
├── config.py               # Settings loaded from environment variables
├── db.py                   # SQLite helpers for runs and scores (parameterised queries only)
├── .env.example            # SECRET_KEY=change-me, FLASK_DEBUG=0 (no real values)
├── requirements.txt
├── README.md
├── game/
│   ├── __init__.py
│   ├── engine.py           # Game class: physics, collision, state machine, score, lives
│   ├── level.py            # Loading and validating level JSON, pellet IDs
│   └── validation.py       # Plausibility checks used by the server
├── levels/
│   ├── level_1.json
│   ├── level_2.json
│   └── level_3.json
├── templates/
│   └── index.html          # The one page, for both modes
├── static/
│   └── js/
│       ├── main.js         # Loads Pyodide, game loop, input, canvas drawing, score table
│       └── api.js          # fetch wrappers (server mode), localStorage scores (static mode)
├── scripts/
│   ├── bundle_engine.py    # Zips game/ for Pyodide
│   └── build_static.py     # Builds docs/ for GitHub Pages
├── docs/                   # Generated static build served by GitHub Pages (committed)
└── tests/
    ├── test_physics.py
    ├── test_levels.py
    ├── test_scoring.py
    ├── test_progress.py    # validation.check_progress
    ├── test_api.py         # Flask test client
    └── test_static_build.py
```

### 5.4 Tech Stack

| Component | Choice |
|---|---|
| Language | Python 3.12+ |
| Web framework | Flask 3.x |
| Config loading | `python-dotenv`, so that `flask run` reads `.env` automatically |
| In-browser Python | Pyodide (pinned version, loaded from the jsDelivr CDN) |
| Database | SQLite through the standard-library `sqlite3` module |
| Front end | HTML5 Canvas, vanilla JavaScript, CSS |
| Tests | pytest |
| Hosting | GitHub Pages (static build). Flask runs locally. |

### 5.5 Alternatives Considered

**pygame (through pygbag, or pygame-ce in Pyodide): rejected.** Plain pygame is desktop-only. Its browser builds would move drawing and input into Python too, but they have four costs:
- The page would be little more than a generated canvas. The brief asks for an HTML/CSS web interface, and the HUD, menus and the text-safe high-score table (FR-27) would have to be drawn in pygame instead.
- Calling Flask goes through an awkward JavaScript bridge (`platform.window`).
- It brings constraints of its own: the main loop must be `async`, sound files must be `.ogg`, and errors come from WebAssembly and are hard to read.
- It fetches its runtime from its own CDN and generates its own page. That gives Part 2 less control over pinned versions, integrity hashes and a Content Security Policy.

The pure-Python `game/` engine (NFR-06) keeps a pygame front end possible later without changing the engine or its tests.

## 6. Functional Requirements

Priorities: **M** = Must, **S** = Should, **C** = Could.

### 6.1 Player and Movement
| ID | Requirement | Pri |
|---|---|---|
| FR-01 | Nom is drawn as a circle with an animated wedge mouth and faces the direction of movement. | M |
| FR-02 | Left and right input accelerates Nom horizontally up to a maximum speed; releasing the key applies friction. | M |
| FR-03 | Gravity pulls Nom down every step, up to a terminal velocity. Constraint: `TERMINAL_VY × (1/60) < TILE_SIZE`, so Nom can never move a full tile in one step. This is what prevents tunnelling through a 1-tile floor. `constants.py` asserts it at import time. | M |
| FR-04 | Jumping applies an upward impulse only when `on_ground` is true. Holding the key does not cause repeated jumps. | M |
| FR-05 | Releasing jump early cuts the jump short (variable jump height). **Done:** on release while rising, upward speed is capped at `JUMP_CUT_SPEED` (240 px/s), so a 1-frame tap rises about 24 px and a full hold about 108 px. | C |

### 6.2 Collision and World
| ID | Requirement | Pri |
|---|---|---|
| FR-06 | Collision uses axis-aligned bounding boxes against solid tiles, resolved one axis at a time (X, then Y), so Nom lands on platforms, bumps their undersides and is blocked by walls. | M |
| FR-07 | Nom cannot move past the left or right edge of the level. | M |
| FR-08 | Falling below the bottom of the level costs a life. | M |
| FR-09 | Overlapping a hazard tile (bramble spikes) costs a life. | M |
| FR-10 | After losing a life, Nom respawns at the level start. Pellets already collected in that level stay collected. | M |
| FR-11 | The camera scrolls horizontally (and vertically in Level 3) to keep Nom in view. | M |

### 6.3 Levels and Progression
| ID | Requirement | Pri |
|---|---|---|
| FR-12 | The game contains three distinct, original levels as described in §4.3. | M |
| FR-13 | Level files are validated against §4.5 when loaded: required keys, known tile codes, exactly one start and one goal, sensible dimensions, valid pellet IDs and positions. Invalid files cause a clear error and are never partly loaded. | M |
| FR-14 | Touching the Moon Gate completes the level, awards a completion bonus and moves to the next level without reloading. | M |
| FR-15 | Completing Level 3 shows a win screen with the final score. | M |
| FR-16 | Losing the last life shows a game-over screen. | M |
| FR-17 | Pressing R during play restarts the current level. It clears the pellets collected in that level, removes their points from the score and resets `level_time`, but keeps the lives and the score from earlier levels. Pressing R on the game-over or win screen restarts the whole game: Level 1, 3 lives, score 0. In server mode it also starts a new run (FR-24a). | M |

### 6.4 Scoring and Collectibles
| ID | Requirement | Pri |
|---|---|---|
| FR-18 | Each level contains firefly pellets with IDs that are unique across all levels (`L<level>-P<nn>`, §4.5). Each is worth 10 points and can be collected once. | M |
| FR-19 | Finishing a level awards a bonus of 100 points. | M |
| FR-20 | A HUD always shows the level number and name, the score, the remaining lives, and pellets collected out of the total. | M |
| FR-21 | Title, pause, level-complete, game-over and win screens show instructions and the relevant keys. | M |

### 6.5 Server Mode: Progress and High Scores
| ID | Requirement | Pri |
|---|---|---|
| FR-22 | `GET /` serves the game page. | M |
| FR-23 | `GET /api/levels/<n>` returns the JSON for levels 1–3 and 404 for anything else. | M |
| FR-24a | `POST /api/runs` starts a new run. It is called when the player presses Enter on the title screen or restarts from game-over or win. The server creates a row in the `runs` table, puts only its random `run_id` in the signed session cookie, and discards any previous run for that session. | M |
| FR-24 | `POST /api/progress` records the completion of a level for the current run, including the collected pellet IDs and elapsed time. Progress is stored **server-side** in the `runs` table, keyed by `run_id`. | M |
| FR-25 | `POST /api/scores` accepts a player name and requests a high-score entry. The server **calculates** the score from the progress it has already accepted for that run. The client never sends the score. The run is then marked `submitted` in the database, so replaying an old cookie cannot submit the same run again. | M |
| FR-26 | `GET /api/scores` returns the top 10 scores. | M |
| FR-27 | The front end shows the top-10 table on the title and win screens and inserts names as **text, not HTML**. | M |
| FR-28 | Unknown routes and server errors return a generic JSON or HTML error page with no stack traces. | S |

### 6.6 Static Mode
| ID | Requirement | Pri |
|---|---|---|
| FR-29 | The static build plays all three levels with no server. | M |
| FR-30 | High scores are stored in `localStorage`, and the page shows "local scores only". | S |
| FR-31 | A loading indicator is shown while Pyodide downloads. | M |

## 7. API Specification (server mode)

| Method | Path | Request | Response | Validation |
|---|---|---|---|---|
| GET | `/api/levels/<int:n>` | — | Level JSON | `n` ∈ {1, 2, 3}, otherwise 404 |
| POST | `/api/runs` | `{}` | `{"ok": true}` | Creates a new run and sets the session cookie |
| POST | `/api/progress` | `{"level": int, "pellets": [str], "time": float}` | `{"ok": true, "score": int}` | The session must have an active, unsubmitted run; `level` must equal that run's `next_level`; every pellet ID must exist in that level, with no duplicates; `min_time ≤ time ≤ max_time` from the level file; correct JSON types (a bool is not accepted as an int) |
| POST | `/api/scores` | `{"name": str}` | `{"ok": true, "rank": int}` | Name is trimmed, then must be 1–16 characters from `[A-Za-z0-9 _-]` and not all spaces or underscores; the run must have completed at least one level and must not already be `submitted` |
| GET | `/api/scores` | — | `[{"name", "score", "levels_completed", "created_at"}]` | Maximum 10 rows, ordered by score descending, then by `created_at` ascending |

**Rules for all endpoints:**
- Requests and responses use `application/json`.
- POST requests without `Content-Type: application/json` get 415. Browsers can't send that header cross-site without a CORS preflight, which the app never approves, so this is the first line of defence against CSRF. Part 2 reviews whether it is enough.
- Request bodies over 4 KB are rejected (`MAX_CONTENT_LENGTH`).
- Invalid input gets 400 with a generic message.

`rank` is 1 plus the number of stored scores strictly greater than the new score, so tied scores share a rank.

## 8. Data Model

**SQLite table `scores`**

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `name` | TEXT NOT NULL | Validated, maximum 16 characters |
| `score` | INTEGER NOT NULL | Calculated by the server |
| `levels_completed` | INTEGER NOT NULL | 1–3 |
| `created_at` | TEXT | ISO-8601 UTC |

**SQLite table `runs`**

| Column | Type | Notes |
|---|---|---|
| `run_id` | TEXT PK | `secrets.token_urlsafe(16)` |
| `next_level` | INTEGER NOT NULL | 1–3, or 4 once Level 3 is complete |
| `accepted_score` | INTEGER NOT NULL | Calculated by the server from accepted progress |
| `levels_completed` | INTEGER NOT NULL | 0–3 |
| `submitted` | INTEGER NOT NULL | 0 or 1 |
| `created_at` | TEXT | ISO-8601 UTC. Runs older than 24 hours are rejected and purged. |

**Flask session (signed cookie):** `run_id` only. All progress state lives in `runs`. The cookie is signed, but a user can still save an old cookie and send it again later. Keeping the state on the server means that a replayed cookie points to the same run, which is already marked `submitted`, and so gains the user nothing.

All SQL uses parameterised queries. The DB file lives in `instance/`, which is git-ignored.

## 9. Trust Boundaries and Security Considerations

These are design-level notes that Part 2 will build on.

- **Client-controlled inputs:** keyboard input, all JSON bodies, the URL path segment `n`, the session cookie (signed, but replayable), `localStorage`, and request headers.
- **Python in the browser is still client-side.** Running the engine in Pyodide does **not** make it trustworthy. A user can change Pyodide state from the browser console. The server must treat every value it receives as untrusted.
- **What the server checks:** level order, that pellet IDs exist, that time is plausible, and the score, which the server calculates itself. All of these are checked against the server-side `runs` row, never against values in the cookie.
- **Cookie replay:** handled by design (§8). The cookie holds only `run_id`, and the `submitted` flag lives in the database.
- **What the server cannot check:** whether the player really played, as opposed to scripting valid-looking requests. This limitation will be documented. A deterministic input-log replay on the server is a possible stretch goal (§13).
- **CSRF:** the app uses cookie-authenticated JSON POSTs and requires `Content-Type: application/json` (§7). Part 2 decides whether to add `SameSite=Strict` cookies or a CSRF token.
- **Third-party code:** Pyodide loads from jsDelivr at a pinned version, with a Subresource Integrity (`integrity`) hash on the `pyodide.js` script tag. Part 2 reviews a Content Security Policy for the page.
- **Static mode:** has no server-side trust at all. Scores there are local only and labelled as such.
- **Not present by design:** OS command execution, file uploads and filenames supplied by users. One route does serve files by path: Flask adds `GET /static/<path:filename>` automatically (recorded in `security/baseline.md`); the app defines no file route of its own. Level files are chosen by an integer that is checked against an allow-list, never by a path the user supplies. The engine reaches the browser as one fixed bundle (`game.zip`).
- **Configuration:** `SECRET_KEY` comes from an environment variable or `.env` (loaded by `python-dotenv`), and a `.env.example` is committed without real values. If `SECRET_KEY` is missing or still `change-me`, the app refuses to start. It never falls back to a default key. Debug mode is off unless `FLASK_DEBUG=1` is set.

## 10. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | Runs at a steady 60 FPS in current Chrome and Firefox on a typical laptop once Pyodide has loaded. |
| NFR-02 | The static build is playable within about 10 seconds on a normal connection. Pyodide is pinned and loaded from the CDN. |
| NFR-03 | Input feels immediate: a key press affects the next simulation step. |
| NFR-04 | The README lets a new user install and run server mode in 5 commands or fewer. |
| NFR-05 | All assets are original: canvas-drawn shapes, plus optional CC0 fonts or sounds with credit. |
| NFR-06 | `game/` has no imports from Flask, `js` or Pyodide, so it can be unit-tested with plain pytest. |
| NFR-07 | The code is readable and commented where the logic is not obvious, especially the collision code. The author can explain every module. |
| NFR-08 | A student who downloads the repo can play the game by following the README alone, using either `flask run` or the static build served with `http.server`. Opening `index.html` from disk is documented as unsupported. |

## 11. Testing Requirements (pytest)

| Area | Example tests |
|---|---|
| Physics | Gravity speeds Nom up to terminal velocity; landing sets `on_ground`; jumping is ignored in mid-air; walls stop horizontal movement; no tunnelling through a 1-tile floor at maximum fall speed; the FR-03 constraint holds. |
| Hazards and boundaries | Touching spikes costs a life; falling off the bottom costs a life; losing at 0 lives sets `game_over`. |
| Levels | All three level files load and pass validation; malformed level JSON is rejected (unknown tile, two starts, no goal, ragged rows, pellet on a solid tile); pellet IDs are unique across all levels; level 3 → `won`. |
| State machine | Restarting a level and restarting the game each reset the right fields (FR-17); a pellet is counted only once; score maths is correct. |
| API | Valid progress is accepted; out-of-order levels, unknown pellets, pellets from another level, duplicate pellets, negative or huge times, wrong types (including `true` sent as a level) and missing fields all return 400; levels outside 1–3 return 404; a non-JSON content type returns 415; names with HTML, over-long names and all-space names are rejected; the client cannot set the score; replaying a cookie saved before submission cannot submit the run again; `POST /api/runs` resets progress. |
| Regression checklist | The manual playthrough checklist from Part 2 §15 (movement, jumping, collision, each level, transitions, win, lose, restart, controls, visuals). |

## 12. Milestones

Part 1 core: M0–M4, M6, M7. M5 is built after the core and feeds Part 2 (see §2, Scope priority).

| # | Milestone | Done when |
|---|---|---|
| M0 | Project setup | Repo, Cursor project, folder structure, README stub, this PRD and the one-page design spec committed. Cursor has been asked to **explain** the proposed architecture, and the explanation is saved in the journal (session 1). |
| M1 | Minimum playable game | Canvas, Nom, one floor, left/right movement, jump, keyboard input and a goal, all running through Pyodide and the `game/` engine. Pyodide loading (`game.zip` + `unpackArchive`) is proven here first, because it is the riskiest part of the setup. |
| M2 | Platform mechanics | Gravity, axis-separated collision, boundaries, hazards and lives, with pytest coverage. Cursor has been asked to explain the collision algorithm in plain language, and the author can answer "How does the program know Nom is standing on a platform?" and "What happens when Nom overlaps a hazard?" |
| M3 | Three levels | Level JSON plus validation (§4.5), transitions, and the win and game-over screens. |
| M4 | Feedback and scoring | HUD, pellets, score, message screens and restart. |
| M6 | Static build and deploy | Build script, a live GitHub Pages URL, and the local `http.server` instructions tested from a fresh clone. |
| M7 | Part 1 documentation | Journal (5+ sessions), 3+ debugging write-ups, AI-code analysis, final README and a 500–750-word reflection, all using the §14 templates. |
| M5 | Server mode | Flask routes, `runs` table, SQLite high scores, validation and API tests. |
| M8 | Part 2 security review | Baseline, findings table, fixes, security tests, before/after comparison, reports, security journal and reflection. |

## 13. Stretch Goals (Could)
- Server-side replay: the client sends a compact input log, and the server re-runs the deterministic engine to confirm that the level was completed.
- Coyote time. (Variable jump height is done; see FR-05.)
- Simple sound effects (WebAudio-generated) and a particle burst when a pellet is collected.
- A per-level timer shown in the HUD.

## 14. Deliverables Checklist

**Part 1**
- [ ] Playable game on the author's GitHub Pages site (URL in README)
- [ ] GitHub repo or zip with Python, HTML/CSS/JS, `requirements.txt` and `README.md`
- [ ] One-page game design specification (§4, exported)
- [ ] Vibe-coding journal: 5 or more sessions
- [ ] 3 or more debugging problems documented
- [ ] AI-generated code analysis (recommended target: `game/physics.py` collision resolution)
- [ ] Final reflection (500–750 words)

**README must cover:** what the game is, installing Python and the dependencies, starting the app (server mode, and the static build served locally), the URL to open, controls, how to play, how the levels work, what Python does in the app, and which AI tools were used.

**Documentation templates (fields required by the brief):**

| Document | Fields |
|---|---|
| Journal entry (one per session, 5+) | Date/session · Goal · Prompt(s) used · What Cursor generated · What I tested · What worked · What failed · What I changed · What I learned |
| Debugging write-up (3+) | What I expected · What actually happened · The prompt I gave Cursor · What Cursor suggested · Whether it worked · What I changed · What I learned |
| AI-code analysis (1) | What does the code do? · Why is it necessary? · What inputs does it use? · What output or state does it change? · What assumptions does it make? · What could go wrong? · How did I test it? · Did I modify the AI version, and why? |
| Reflection (500–750 words) | How Cursor changed my approach · Most useful prompts · Poor or incorrect prompts · How I judged correctness · A significant bug and its diagnosis · What I understand most confidently · What needs more study · Advantages of vibe coding for beginners · Risks of over-reliance · What I would redesign |

**Part 2** (planned)
- [ ] Hardened game, plus updated dependencies and README
- [ ] Security architecture and data-flow diagram
- [ ] Findings table, plus a report for each finding
- [ ] Security tests, results from automated tools, and evidence of dependency analysis
- [ ] Before/after comparison
- [ ] 5 or more security journal entries
- [ ] Security reflection (750–1,000 words)

## 15. Open Questions
1. ~~Will the instructor accept server mode running only locally?~~ **Resolved.** The brief requires the game on GitHub Pages and also that it can be downloaded and run locally. The static build covers both, and server mode runs locally only.
2. Which automated security tool should Part 2 use (OWASP ZAP, bandit, pip-audit)? Does the instructor need to approve it?
3. **Decided, pending instructor confirmation:** load Pyodide from the jsDelivr CDN at a pinned version with an SRI hash, and say in the README that an internet connection is needed on first load. Fallback: store the Pyodide core files in the repo (about 10–15 MB, never the full package set) if offline play is required.
