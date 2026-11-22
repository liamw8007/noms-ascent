# Part 15: Regression Testing

Run on 2026-11-22, on branch `hardening` after all Part 14 fixes, with Pyodide 314.0.8 hosted
by the site.

## 1. Automated tests

`pytest` passes all 240 tests (`evidence/pytest-after.txt`). That covers the engine physics,
collision, levels, scoring and progress, the API, the static build and the security suite. The
dependencies were installed from the hash-pinned `requirements-dev.txt` in a clean virtual
environment.

## 2. Browser replay of the game requirements

**Script:** `security/browser-check/regression.mjs`, driving headless Chromium.

**Run:** `bash security/browser-check/run.sh regression.mjs <screenshot-dir>`. It runs once in
**server mode** (Flask) and once in **static mode** (`docs/`, as on GitHub Pages).

**Full output:** `evidence/browser-regression.md`. **Screenshots:** `evidence/screenshots/`.

**How it plays:** movement, jumping, help, restart and name entry use **real key events**. To
get through whole levels in reasonable time, the script moves Nom onto pellets, spikes or the
Moon Gate through the engine object. It first waits real time in each level, so the server's
new clock check (SEC-01) is exercised rather than bypassed.

| Requirement | Server | Static |
|---|---|---|
| Player movement (Arrow keys, A/D) | ✅ | ✅ |
| Jumping: a held jump rises 108 px (~3.4 tiles), a tap 24 px | ✅ | ✅ |
| Collision: lands back on the floor; the world edge stops Nom | ✅ | ✅ |
| Level 1 works: pellets +10, a fall costs a life, pellets kept after a death | ✅ | ✅ |
| Level 2 works: spikes cost a life | ✅ | ✅ |
| Level 3 works | ✅ | ✅ |
| Level transitions: the Moon Gate shows "level complete", Enter goes to the next level | ✅ | ✅ |
| Winning: "You reached the final Moon Gate!", final score 330 | ✅ | ✅ |
| Losing: three falls → game over | ✅ | ✅ |
| Restart: R restarts the level (points removed, no life lost); R after a win or loss starts a new game | ✅ | ✅ |
| Keyboard controls: `?` opens help and pauses the game, Esc resumes; R is ignored while typing a name | ✅ | ✅ |
| Server scoring: each level is accepted, and the server's score equals the engine's (110, 220, 330) | ✅ | n/a |
| Score saving: the name and score appear in the top-10 table; static mode says "local scores only" | ✅ | ✅ |
| Visual elements: Nom, HUD, overlays and score table drawn (see screenshots) | ✅ | ✅ |
| No CSP violations, no JavaScript errors, no requests to other sites | ✅ | ✅ |
| **Total** | **35/35** | **32/32** |

## 3. Security checks re-run after the fixes

- **SEC-05:** `csp-check.mjs`. An injected inline script and `onerror` handler were blocked,
  and framing from another origin was refused (`evidence/browser-csp-check.json`).
- **SEC-09:** `loadfail.mjs`. With the engine download blocked, both modes show "The game
  failed to load. Please reload the page." The details appear only in the console
  (`evidence/browser-loadfail.json`).
- **SEC-04:** Chromium stored the session cookie as `Secure`, `HttpOnly`, `SameSite=Strict`
  with a 24 h lifetime, and page scripts couldn't read it. It still sent the cookie over
  `http://127.0.0.1`, so local server mode keeps working.
- **Static analysis and dependencies:** bandit and pip-audit were re-run (see
  `automated-testing.md`, `evidence/pip-audit-after.txt`).

## Functional changes caused by the fixes

| Fix | Effect on play | Removed functionality? |
|---|---|---|
| SEC-01 server clock | None for a real player. A level reported faster than the server's clock (plus 2 s slack) is rejected. | No |
| SEC-02 limits | Only the best 100 scores are kept. A new run gets 503 if 10,000 runs are active. | No (the top 10 is unaffected) |
| SEC-03 Pyodide 314 | Python 3.14 in the browser instead of 3.12. The first load is 13 MB from the site, and the game no longer needs internet access. | No |
| SEC-04 cookie | A server-mode run expires 24 h after it starts (it already did on the server). | No |
| SEC-06 key length | An existing `.env` with a key shorter than 32 characters must be regenerated. | No |
| SEC-07 lock files | `pip install --require-hashes -r requirements.txt`; tests need `requirements-dev.txt`. | No |
| Others | No visible change | No |

## Not yet done (by the author)

- [ ] A manual playthrough of all three levels in a normal browser (Firefox or Chrome), since
  the automated run moves Nom between points.
- [ ] Check the GitHub Pages deployment once `hardening` is merged into `main`.
