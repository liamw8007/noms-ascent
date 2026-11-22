# Security Findings

The version reviewed is the tag `v2-pre-review` (commit `9d927b4`). Fixes are on the branch
`hardening`.

Sources:
- **Blind review:** the AI review run without the project notes, 11/19 (`Nom's Ascent Security
  Findings.pdf`, findings 1–8).
- **Follow-up reviews:** Claude Code sessions, 11/22: XSS, injection, paths, secrets, sessions
  and dependencies.
- **Known:** issues already recorded before the review started.

"Verified?" means a test showed the problem is real. Every finding marked Yes has a test in
`tests/test_security.py` that failed on the unfixed code (`security/evidence/pytest-before.txt`).

| ID | Finding | Location | Severity | Verified? | Source | Remediation | Status |
|---|---|---|---|---|---|---|---|
| SEC-01 | Leaderboard scores can be faked: the server trusts the client's completion time, so a script can claim every pellet at `min_time` straight away | `app.py` `progress()`, `game/validation.py` `check_progress()` | High | Yes | Blind #1 | Time each level with the server's clock and reject reports faster than real time | Open |
| SEC-02 | No limits: every `POST /api/runs` adds a row, and `scores` is never trimmed, so the disk can be filled | `app.py` `new_run()`, `db.py` `start_run()`, `submit_score()` | Medium | Yes | Blind #2 | Cap active runs (503 when full), keep only the top scores, WAL mode; per-IP limits at the proxy | Open |
| SEC-03 | Pyodide is loaded from a CDN with no integrity check and no CSP, and it is out of date (0.27.2) | `templates/index.html:36` | Medium | Yes | Blind #3, follow-up (deps), known | Host Pyodide 314.0.8 ourselves; CSP allows `'self'` only | Open |
| SEC-04 | Session cookie lacks `Secure` and `SameSite` and has no lifetime; a copied cookie takes over the run | `config.py`, `app.py` `new_run()` | Medium (blind review: Low; raised after the cookie-copy test) | Yes | Blind #4, follow-up (sessions) | `Secure`, `SameSite=Strict`, 24 h `Max-Age`; HTTPS + HSTS in deployment | Open |
| SEC-05 | No security response headers: no CSP, `nosniff`, framing protection or `Referrer-Policy` | `app.py` (no `after_request`) | Low | Yes | Blind #5, known (CSP) | `after_request` hook, plus a CSP `<meta>` tag for the static build | Open |
| SEC-06 | Weak `SECRET_KEY` values are accepted; only an empty key and `change-me` are refused | `config.py` `load_config()` | Low | Yes | Blind #6 | Require at least 32 characters | Open |
| SEC-07 | Dependency hygiene: indirect dependencies unpinned with no hashes, pytest mixed into the runtime dependencies, no production server documented | `requirements.txt`, README | Low | Yes | Blind #7, follow-up (deps) | Full hash-pinned lock files, separate `requirements-dev.txt`, deployment notes | Open |
| SEC-08 | CSRF defence relies on one control, the `application/json` check | `app.py` `require_json_posts()` | Info | Yes | Blind #8 | `Origin` check on POSTs, plus `SameSite=Strict` (SEC-04) | Open |
| SEC-09 | Raw error text is shown to the player when loading fails | `static/js/main.js` (last line) | Low | Yes | Known | Fixed message on the page; details only in the console | Open |
| SEC-10 | The build follows symlinks, so a symlink in `static/` or `game/` would publish its target (e.g. `.env`) | `scripts/build_static.py` `build()`, `scripts/bundle_engine.py` `make_zip()` | Low | Yes | Follow-up (paths) | Refuse symlinks | Open |
| SEC-11 | The static build renders the template without HTML escaping (latent: the only value is a constant) | `scripts/build_static.py` `build()` | Info | Yes (by code reading; the test needs a helper that didn't exist yet) | Follow-up (XSS) | `Environment(autoescape=True)` | Open |
| SEC-12 | Compiled `.pyc` files in early git history contain local absolute paths (username, folder layout) | commits `51c93d1`, `81e4a0d` | Info | Yes | Follow-up (secrets) | None: rewriting pushed history would change the `v1-original` tag | Accepted risk |

## Accepted limitations (by design, not fixed)

- **Lives and in-game state are client-side only.** The engine runs in the browser, so a player
  can edit lives in their own tab. The server never accepts lives (`test_lives_are_not_accepted_from_the_client`),
  and it calculates the score itself.
- **A patient script can still submit a high score** after SEC-01 by waiting out real time and
  claiming every pellet. A complete fix needs the server to replay every frame of input (PRD §9).
- **Static mode keeps scores in `localStorage`**, which the player can edit. They are local
  scores only (FR-30) and are re-checked when loaded.

## Verified controls (claims tested and found to hold)

| Area | Control | Evidence |
|---|---|---|
| SQL injection | Every query uses `?` placeholders | `' OR 1=1--` and `'); DROP TABLE scores;--` sent straight into `db.py` were stored as text, and the tables stayed intact |
| XSS | Score names inserted with `textContent`, levels drawn on the canvas, `NAME_RE` on the server | `<img onerror>`, `<script>` and `<svg onload>` written straight into SQLite showed as text in headless Chromium |
| Path traversal | Werkzeug `safe_join`; levels picked by index | `../app.py`, `%2e%2e%2f.env` and `..%2f..%2fapp.py` all returned 404 |
| Client-set score | The score is calculated by the server | `test_the_score_is_calculated_by_the_server` |
| Cookie tampering and replay | Signed cookie; `submitted` flag in the DB | A tampered signature, a key forged with `change-me` and an old cookie after a new run all returned 400 |
| Secrets | No secrets in the tree or history; `.env` never committed | Masked regex scan of 60 blobs; `SECRET_KEY` only from the environment |
| Error handling | Generic JSON errors; no stack traces | `test_errors_are_generic_json`, `test_an_unexpected_exception_is_a_generic_500` |
