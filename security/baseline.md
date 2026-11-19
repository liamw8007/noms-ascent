# Part 1 — Security Baseline

This document records the application **as it was before the security review**, so that later
fixes can be compared against it. Nothing here has been changed or fixed yet.

## Version under review

| | |
|---|---|
| Baseline snapshot | Git tag `v2-pre-review` (commit `9d927b4`), created before any review or hardening |
| Earlier version | Tag `v1-original` (commit `81e4a0d`): the Part 1 submission, a static, browser-only game |
| What changed between them | v2 added an optional Flask server ("server mode") with a level API, a high-score table in SQLite and server-side checks on reported progress. The static GitHub Pages build still exists. |
| Date recorded | 2026-11-19 |

The game has **two run modes**, and both are in scope:

- **Server mode:** `flask --app app run`, http://127.0.0.1:5000. Flask serves the page and the API.
- **Static mode:** GitHub Pages, or the `docs/` folder served by any static web server. There is no
  Python server; everything runs in the browser.

## Inventory

### Python version

| Where Python runs | Version |
|---|---|
| Server (Flask), tests and build scripts | CPython 3.14.10 (development machine) |
| Browser (game engine, both modes) | CPython 3.12.7 compiled to WebAssembly, bundled in Pyodide 0.27.2 |

### Web framework

Flask 3.1.3, running on Werkzeug 3.1.9 (Werkzeug supplies routing, request parsing and the
development server). Pages are rendered with Jinja2 3.1.6.

### Third-party packages

Direct dependencies are pinned in `requirements.txt`; the other packages are installed with them.

| Package | Version | Why it is there | Used at |
|---|---|---|---|
| Flask | 3.1.3 | Web framework (server mode); its Jinja2 also renders the static build | Runtime, build |
| python-dotenv | 1.2.4 | Lets `flask run` read `SECRET_KEY` from `.env` | Runtime |
| pytest | 9.2.0 | Test runner | Development only |
| Werkzeug | 3.1.9 | Installed with Flask: HTTP handling, dev server | Runtime |
| Jinja2 | 3.1.6 | Installed with Flask: HTML templates (autoescaping on for `.html`) | Runtime, build |
| itsdangerous | 2.2.0 | Installed with Flask: signs the session cookie | Runtime |
| MarkupSafe | 3.0.4 | Installed with Jinja2: HTML escaping | Runtime |
| click | 8.5.1 | Installed with Flask: the `flask` command | Runtime |
| blinker | 1.9.0 | Installed with Flask: signals | Runtime |
| iniconfig, pluggy, packaging, Pygments | 2.3.1, 1.7.0, 26.3, 2.21.0 | Installed with pytest | Development only |
| **Pyodide** (not a pip package) | 0.27.2 | Runs the Python game engine in the browser | Browser, loaded from jsDelivr |

The game engine (`game/`) itself uses only the Python standard library.

### Application entry points

| Entry point | What it starts |
|---|---|
| `app.py` → `create_app()` | The Flask application factory. Started with `flask --app app run` (Werkzeug development server). |
| `templates/index.html` | The one HTML page, rendered with `mode="server"` by Flask or `mode="static"` by the build script |
| `static/js/main.js` → `main()` | The browser side: loads Pyodide, unpacks the engine, starts the game loop |
| `scripts/build_static.py` | Developer tool: builds the static site into `docs/` |

### Routes and endpoints (server mode)

Taken from Flask's own route table (`app.url_map`), not just from reading the code. HEAD and
OPTIONS are added automatically by Flask and are not listed.

| Method | Route | Input from the client | Purpose |
|---|---|---|---|
| GET | `/` | none | The game page |
| GET | `/static/<path:filename>` | **a file path** (`filename`) | **Added automatically by Flask.** Serves files from `static/` (`main.js`, `api.js`) |
| GET | `/engine/game.zip` | none | The `game/` package as a zip, built in memory when the app starts |
| GET | `/api/levels/<int:n>` | path segment `n` | Level data (grid, name, `min_time`, `max_time`) for level `n` |
| POST | `/api/runs` | JSON body (ignored), session cookie | Starts a new run and sets the session cookie |
| POST | `/api/progress` | JSON `{level, pellets, time}`, session cookie | Reports a finished level; the server checks it and adds the points |
| POST | `/api/scores` | JSON `{name}`, session cookie | Saves the run's server-calculated score under a name |
| GET | `/api/scores` | none | The top 10 scores |

There are no other routes: no admin pages, no file uploads and no debug endpoints.

In **static mode** there are no endpoints. The static host serves `index.html`, `static/js/*.js`,
`engine/game.zip` and `levels/level_1.json`–`level_3.json` as plain files.

### Client-side JavaScript

| File | Origin | What it does |
|---|---|---|
| `static/js/main.js` | This project | Loads Pyodide, fetches and unpacks `engine/game.zip`, fetches the levels, reads the keyboard, runs the fixed-timestep loop, draws on the canvas, shows the high-score table and the name form |
| `static/js/api.js` | This project | `fetch()` wrappers for the four `/api/runs|progress|scores` calls (server mode); `localStorage` score store (static mode) |
| `pyodide.js` | jsDelivr CDN, `https://cdn.jsdelivr.net/pyodide/v0.27.2/full/` | Pyodide's loader. It then downloads the rest of the Python runtime (WebAssembly binary, standard library) from the same CDN folder. |
| The `game/` Python package | This project, delivered as `engine/game.zip` | The game rules (physics, collision, score, lives), running in the browser through Pyodide |

There is no inline JavaScript in the page and no other third-party script.

### Data stored by the application

| Data | Where | Mode | Written by |
|---|---|---|---|
| `runs` table: `run_id`, `next_level`, `accepted_score`, `levels_completed`, `submitted`, `created_at` | SQLite, `instance/scores.db` | Server | `POST /api/runs`, `/api/progress`, `/api/scores` |
| `scores` table: `id`, `name`, `score`, `levels_completed`, `created_at` | SQLite, `instance/scores.db` | Server | `POST /api/scores` |
| Session cookie `session`: holds only `run_id`, signed with `SECRET_KEY` (itsdangerous HMAC), not encrypted | The browser | Server | `POST /api/runs` |
| `noms-ascent-scores`: up to 10 `{name, score, levels_completed, created_at}` entries | The browser's `localStorage` | Static | The name form |
| Game state (position, lives, score, collected pellets, level time) | Memory, inside Pyodide in the browser | Both | The engine |
| Level data and the engine zip | Server memory, loaded once at startup | Server | `create_app()` |

No personal data is collected apart from the free-text player name, which is limited to 1–16
letters, digits, spaces, `_` or `-`.

### Configuration files

| File | In Git? | Contents |
|---|---|---|
| `.env` | **No** (in `.gitignore`) | `SECRET_KEY`, `FLASK_DEBUG`. Created by the person running the server. |
| `.env.example` | Yes | Placeholders only: `SECRET_KEY=change-me`, `FLASK_DEBUG=0` |
| `config.py` | Yes | Reads `SECRET_KEY`; refuses to start if it is missing or `change-me` |
| `app.py` (`create_app`) | Yes | `MAX_CONTENT_LENGTH` = 4 KB; database path; everything else uses Flask defaults |
| `levels/level_N.json` | Yes | Level grids plus `min_time`/`max_time`, which the server uses to judge reported times |
| `requirements.txt` | Yes | Pinned Python dependencies |
| `pytest.ini` | Yes | Test settings |
| `templates/index.html` | Yes | The pinned Pyodide URL (`v0.27.2`) |

Flask settings left at their defaults that matter for security (read from `app.config`):

| Setting | Value at baseline |
|---|---|
| `DEBUG` | `False` (unless `FLASK_DEBUG=1` is set) |
| `SESSION_COOKIE_HTTPONLY` | `True` |
| `SESSION_COOKIE_SECURE` | `False` |
| `SESSION_COOKIE_SAMESITE` | `None` (not set) |
| Session lifetime | Not a permanent session, so the cookie lasts until the browser closes. The server separately ignores runs older than 24 hours. |

### Environment variables

| Variable | Read by | Effect |
|---|---|---|
| `SECRET_KEY` | `config.py` | Signs the session cookie. Required; there is no default. |
| `FLASK_DEBUG` | The `flask` command (not by this project's code) | `1` turns on debug mode and the Werkzeug interactive debugger |
| `FLASK_RUN_HOST`, `FLASK_RUN_PORT` and other `FLASK_*` | The `flask` command | Where the dev server listens (default `127.0.0.1:5000`) |

`python-dotenv` makes the `flask` command load these from `.env` (and `.flaskenv`, which does not
exist in this project).

### Files written by the application

| File | When |
|---|---|
| `instance/` (folder) | Created by `create_app()` if missing |
| `instance/scores.db` (plus SQLite's temporary `scores.db-journal` during writes) | Created on startup; written on every POST to `/api/runs`, `/api/progress` or `/api/scores` |

The server writes no log files: Flask logs to the console (stderr). Developer tools write `docs/`
(`build_static.py`) and `__pycache__/`, but the running application does not.

### External services and APIs

| Service | Used for | Mode |
|---|---|---|
| jsDelivr CDN | Downloads Pyodide 0.27.2 into the visitor's browser | Both |
| GitHub Pages | Hosts the static build | Static |

The application calls no other external APIs. The Flask server makes no outgoing requests.

### Authentication and authorization

- **There are no user accounts, passwords or logins.** Anyone who can reach the server can play
  and submit a score.
- The signed session cookie identifies a **run**, not a person. Whoever holds the cookie can act
  on that run.
- The server-side rules that decide what a run may do (from `app.py` and `db.py`):
  - progress is accepted only for the run's `next_level` (levels in order, each once);
  - every pellet ID must exist in that level, with no repeats;
  - the reported time must be between the level's `min_time` and `max_time`;
  - the score is calculated by the server; the client never sends it;
  - a run can submit a score only once, and only after completing at least one level;
  - runs older than 24 hours are ignored.
- In static mode there is no server and therefore no authorization at all.

## Architecture diagram

The brief's template, changed to match this application. `═══` lines are **trust boundaries**:
everything above a boundary is controlled by the user (or a third party) and is untrusted by the
layer below it.

```
                 Player (keyboard, browser console, any HTTP client)
                                   |
                                   v
 ┌──────────────────────────── Browser ─────────────────────────────┐
 │  templates/index.html  (canvas, name form, high-score table)     │
 │        |                                                         │
 │        v                                                         │
 │  static/js/main.js + api.js ──► Pyodide 0.27.2 (Python in WASM)  │
 │    keyboard, game loop,          └─ game/ engine from game.zip:  │
 │    drawing, score table             physics, lives, score, time  │
 │        |                                                         │
 │        +──── localStorage "noms-ascent-scores"  (static mode)    │
 └────────|────────────────────────────────|────────────────────────┘
          |                                |
          |  HTTPS: pyodide.js, .wasm,     |  HTTP (server mode): fetch() JSON,
          |  Python stdlib                 |  session cookie (signed run_id)
          v                                |
 ═══════════════════════                   |      ═══════ trust boundary ═══════
  jsDelivr CDN (third party)               v
                         ┌────────── Flask app (app.py) ───────────┐
                         │  GET  /  /static/<path>  /engine/game.zip│
                         │  GET  /api/levels/<n>    /api/scores     │
                         │  POST /api/runs /api/progress /api/scores│
                         │     |               |                    │
                         │     |               +── Game rules:      │
                         │     |                   game/level.py,   │
                         │     |                   game/validation.py│
                         │     |                   (same code as the│
                         │     |                    browser engine) │
                         │     v                                    │
                         │  db.py ──► SQLite instance/scores.db     │
                         │            (runs, scores)                │
                         │  File system (read once at startup):     │
                         │    levels/*.json, game/*.py, templates/, │
                         │    static/ (read per request)            │
                         │  Config: .env → SECRET_KEY, FLASK_DEBUG  │
                         │  Libraries: Flask, Werkzeug, Jinja2,     │
                         │    itsdangerous, python-dotenv           │
                         └──────────────────────────────────────────┘

 Static mode: the lower half does not exist. GitHub Pages serves the files in docs/,
 levels come from levels/*.json, and scores stay in localStorage.
```

Key point for the review: **the Python engine running in the browser is client-side code.** It
is the same Python as on the server, but the user controls the browser, so nothing the engine
reports can be trusted just because it came from Python.

## Security question: what could an attacker control?

"Attacker" here means anyone who can load the page or send HTTP requests to the server. The
second column says where each input enters; the third says what the baseline does with it
(checked only by reading the code and by quick manual requests, not yet tested thoroughly).

| Input | Can the attacker control it? | Where it enters and what the baseline does with it |
|---|---|---|
| Keyboard input | **Yes** | Read by `main.js` and passed to the engine as left/right/jump. Affects only the attacker's own browser. Automated or scripted input is indistinguishable from a real player. |
| URL parameters | **Yes**, but none are read | No route reads a query string. The only values taken from the URL path are `n` in `/api/levels/<int:n>` (must be an integer; Flask returns 404 otherwise) and `filename` in Flask's built-in `/static/<path:filename>`. |
| Form fields | **Yes** | One field: the player name. It is sent as JSON to `POST /api/scores`; the server trims it and requires 1–16 of `A–Z a–z 0–9 space _ -`. |
| JSON requests | **Yes**, completely | All three POST bodies. Anyone can send them directly (e.g. with `curl`) without loading the game. The server requires `Content-Type: application/json`, limits bodies to 4 KB and checks every field's type and value. |
| HTTP headers | **Yes** | `Content-Type` is checked on POSTs. `Content-Length` is enforced against the 4 KB limit. No other request header (`Host`, `User-Agent`, `Origin`, `Referer`, …) is read by the application's code. |
| Cookies | **Yes** | The `session` cookie. Its signature stops the attacker from **changing** `run_id` without `SECRET_KEY`, but they can read it (it is only base64-encoded), delete it, copy it to another client or replay an old one. |
| Stored game data | **Partly** | Static mode: `localStorage` is fully under the user's control (browser developer tools). Server mode: the database is not directly reachable, but the attacker writes to it indirectly through the API (names, runs). Data read back from either store is displayed in the score table. |
| Game state in the browser | **Yes**, completely | Lives, score, position and timers live in Pyodide in the attacker's browser and can be changed from the console. The server never receives lives or score. |
| Filenames | **Only** through `/static/<path:filename>` | No route takes a filename in a body or query. Level files are chosen by integer `n`, not by name. The Flask static route takes a path; a quick test of `/static/../app.py` and `/static/%2e%2e/app.py` returned 404. |
| Scores | **Indirectly** | The client never sends a score. The server calculates it from the pellet IDs and level completions it accepts, so the attacker controls the score through **which pellets and times they report** (`POST /api/progress`). |
| Level identifiers | **Yes** | `n` in `/api/levels/<n>` and `level` in `POST /api/progress`. Progress must be for the run's `next_level`; a bool is rejected even though Python treats `True` as `1`. |
| Reported time and pellets | **Yes** | `time` (must be a finite number within the level's `min_time`–`max_time`) and `pellets` (list of known, unique IDs for that level). These are claims by the client; the server can check that they are possible, not that they really happened. |
| Configuration values | **No** for remote users | `.env`, `SECRET_KEY` and `FLASK_DEBUG` are set by whoever runs the server. No request can change configuration. If `.env` or `SECRET_KEY` leaked, an attacker could forge session cookies. |
| Third-party code | **Not the attacker directly** | Pyodide is fetched from jsDelivr at a pinned version. Whoever controls that CDN (or the connection to it) controls code running in the page. |

**Summary.** The attacker controls everything that happens in the browser, including the Python
engine, and every byte of every HTTP request. The trust boundary is the Flask server: only
server-side state (the `runs` and `scores` rows) and server-side calculations can be relied on.
In static mode there is no such boundary, so nothing in it can be relied on.

## How this baseline was produced

- Versions: `pip freeze` in the project's virtual environment; Pyodide's own `pyodide-lock.json`
  for the browser Python version.
- Routes and Flask defaults: printed from `app.url_map` and `app.config` of a running
  `create_app()`, so automatically added routes (`/static/…`) are included.
- Behaviour notes: read from the code at `v2-pre-review` plus a few manual requests (`curl` and
  Flask's test client) against a local server with a throwaway database.
