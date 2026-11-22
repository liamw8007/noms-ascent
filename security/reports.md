# Part 17: Security Finding Reports

One report per genuine finding, from `findings.md`. Each **Remediation** starts with the
security requirement written before the code was changed (Part 14: Finding → Understand → Fix
→ Test → Retest → Document), and names the commit on branch `hardening`.

Some details apply to every report, so they aren't repeated below.

**AI sources:**

- **Blind review:** an AI review run without the project notes (`Nom's Ascent Security
  Findings.pdf`, 11/19).
- **Follow-up reviews:** Claude Code sessions with the notes, 11/22.
- Claude Code stood in for Cursor throughout, as the instructor authorised.

**Regression for every fix:** the full `pytest` suite (240 tests) and the browser replay in
both modes (`regression.md`, 35/35 and 32/32).

---

## Finding SEC-01: Leaderboard scores can be faked by a script

**Severity:** High

**Location:**

- `app.py` `progress()`
- `game/validation.py` `check_progress()`
- `db.py` `runs` table

**Description:** `POST /api/progress` accepted the completion time the client reported, if it
was between the level's `min_time` and `max_time`. The level grids, pellet IDs and `min_time`
are all public. A script could therefore start a run and immediately report every level, with
every pellet, at `min_time`.

**Security impact:** anyone can put a perfect score at the top of the shared leaderboard in
milliseconds, making it meaningless. It's an integrity problem, the main asset the server mode
exists to protect.

**Root cause:** the server trusted a value the client controls. Its only defence was a
plausibility range on that same value. The design (PRD §9) accepted that plausibility checks
can't prove a player really played, but never used the one thing the server does control: its
own clock.

**Evidence:** `test_a_script_cannot_finish_a_level_faster_than_real_time` reported level 1 with
all 8 pellets at `min_time`, with no time passing, and got **200** on the original code
(`evidence/pytest-before.txt`).

**AI assistance:** the blind review found it (#1, High), explained the attack and suggested
both the complete fix (replaying inputs on the server) and the quicker one (a server-side
start time). The quicker fix was chosen.

**Remediation:**

- **Requirement:** "The server must not accept a level completion that reports more play time
  than has actually passed on the server since that level began. Real players must not be
  affected."
- **Change (`5ecc59e`):** `runs.level_started_at` is set when a run starts and each time a
  level is accepted. `check_progress()` takes `elapsed`, the time measured by the server, and
  rejects `time > elapsed + CLOCK_SLACK` (2 s, allowing for request latency). An old `runs`
  table is recreated on startup; scores are kept.

**Verification:**

- The three SEC-01 tests now pass: an instant report gets 400 and the same report after
  waiting gets 200; a reported time longer than real time is rejected; each level is timed
  from the previous acceptance.
- `test_progress_faster_than_the_server_clock_is_rejected` checks the slack boundary.
- In the browser, all 3 levels were accepted after real play time, with the server score equal
  to the engine's.

**Regression impact:** existing API tests now advance a fake clock to simulate the time played.
There's no change to play. **Residual risk:** a script that waits out real time can still claim
every pellet. Only replaying inputs on the server would stop that.

---

## Finding SEC-02: No limits on stored runs or scores

**Severity:** Medium

**Location:**

- `app.py` `new_run()`
- `db.py` `start_run()`, `submit_score()`

**Description:** every `POST /api/runs` without a cookie inserted a row, and only runs older
than 24 h were ever deleted. Every saved score stayed in `scores` forever. SQLite allows one
writer at a time.

**Security impact:** an anonymous flood fills the disk (denial of service) and causes "database
is locked" 500 errors for real players.

**Root cause:** the design focused on the correctness of each request and never limited
totals. Rate limiting was out of scope for a course project.

**Evidence:** `test_the_number_of_active_runs_is_capped` (a 4th run with a cap of 3 got
**200**) and `test_only_the_top_scores_are_kept` (5 rows stored with a limit of 3) both failed
on the original code.

**AI assistance:** the blind review found it (#2, Medium) and suggested per-IP rate limiting,
a run cap, trimming scores, a timeout and WAL mode.

**Remediation:**

- **Requirement:** "The database must not grow without limit from anonymous requests. When
  full, refuse new runs with a clear error, not a crash. Never drop a score that is in the
  top 10."
- **Change (`a56f6db`):** `MAX_ACTIVE_RUNS = 10,000` (runs from the last 24 h);
  `start_run()` returns `None` when full, and the route gives **503**. `submit_score()` keeps
  the best `SCORES_KEPT = 100`. WAL mode is on. Per-IP limits are left to the reverse proxy
  (README) to avoid adding a dependency.

**Verification:** both tests pass. Runs are accepted again after the old ones expire (tested
with the fake clock).

**Regression impact:** the top-10 ordering test (`test_top_ten_order_and_shared_ranks`) still
passes, and the browser saved scores.

---

## Finding SEC-03: Third-party, outdated Pyodide with no integrity check

**Severity:** Medium

**Location:** `templates/index.html:36` (original)

**Description:**

- The page loaded `pyodide.js` 0.27.2 from `cdn.jsdelivr.net` with no SRI hash and no CSP.
- The loader then fetched `pyodide.asm.wasm`, `python_stdlib.zip` and the lock file from the
  same CDN, so SRI on the `<script>` tag alone would not have covered them.
- 0.27.2 (Jan 2025) had been replaced by 0.28, 0.29 and 314.x.

**Security impact:** if the CDN or that path were compromised, its code would run as this
site's code. It could read the page, call the API with the player's cookie and fake scores.
The runtime also no longer received fixes.

**Root cause:** the original goal was a quick static deployment. The PRD called for SRI (§9),
but it was never added. Pyodide isn't a pip package, so `pip-audit` never saw it.

**Evidence:**

- `test_the_page_loads_no_third_party_code` found `src="https://` on the original page.
- The npm registry showed 0.27.2 was several releases behind.

**AI assistance:**

- The blind review found the missing SRI and CSP (#3).
- The follow-up dependency review added that the version was out of date, and that SRI only
  protects the loader.

**Remediation:**

- **Requirement:** "The page must run no code from other sites. Every Pyodide file must come
  from this site, at a maintained version, and the browser must refuse scripts from anywhere
  else. The game must still work in both modes."
- **Change (`7a9f2f9`):**
  - The `pyodide@314.0.8` npm tarball was downloaded and its sha512 checked against the
    registry. The core files are in `static/pyodide/`, with their SHA-256 values in its
    README.
  - `loadPyodide({indexURL})` now points at that folder.
  - A CSP `<meta>` tag allows `'self'` plus `'wasm-unsafe-eval'`. The inline `<style>` moved
    to `static/css/game.css`, so `'unsafe-inline'` isn't needed.

**Verification:**

- The test passes.
- In headless Chromium, both modes load all five Pyodide files from the site, with no CSP
  violations and no requests to other sites.

**Regression impact:**

- Python in the browser moves from 3.12 to 3.14. The full browser replay passed in both modes.
- The repo grows by about 13 MB, counted twice because `docs/` is a copy.

---

## Finding SEC-04: Session cookie not hardened

**Severity:** Medium (the blind review rated it Low; it was raised after the cookie-copy test)

**Location:**

- `app.py` `create_app()`, `new_run()`
- `config.py`

**Description:** Flask's defaults were left in place. The header was
`Set-Cookie: session=…; HttpOnly; Path=/`, with no `Secure`, no `SameSite` and no lifetime.

**Security impact:** over plain HTTP the cookie can be sniffed. It works for whoever holds it:
in a test, a second client using a copied cookie finished the run and saved the score, and the
real player's requests were then rejected.

**Root cause:** framework defaults are aimed at development over `http://`, and production
settings were never added.

**Evidence:** `test_session_cookie_flags` failed ("Secure" missing). The cookie-copy test is
described in `security_journal.md`, entry 1.

**AI assistance:**

- The blind review found it (#4).
- The follow-up session review tested the takeover, checked the cookie's other properties and
  proposed the production configuration.

**Remediation:**

- **Requirement:** "The session cookie must only travel over HTTPS (localhost excepted), never
  on cross-site requests, never be readable by scripts, and expire with its run. Local
  development must still work."
- **Change (`44e812f`):** `SESSION_COOKIE_SECURE=True`, `SESSION_COOKIE_SAMESITE="Strict"`,
  an explicit `SESSION_COOKIE_HTTPONLY=True`, `PERMANENT_SESSION_LIFETIME=RUN_LIFETIME` and
  `session.permanent = True`. These are assigned, not `setdefault`, because Flask already has
  these keys.

**Verification:**

- The test passes (flags present; `Expires` about 24 h ahead).
- Chromium stored the cookie as `Secure`, `HttpOnly`, `SameSite=Strict`, 24 h; page scripts
  couldn't read it; and it was sent over `http://127.0.0.1`, where progress returned 200.

**Regression impact:** none. Server mode works locally because browsers treat `127.0.0.1` as
secure. **Residual risk:** a cookie stolen another way still works, as with any cookie session;
the fix reduces the ways to steal one.

---

## Finding SEC-05: No security response headers

**Severity:** Low

**Location:** `app.py` (there was no `after_request` hook)

**Description:** responses had no Content-Security-Policy, `X-Content-Type-Options`,
`X-Frame-Options` / `frame-ancestors` or `Referrer-Policy`.

**Security impact:**

- Without a CSP, any future XSS bug would be fully exploitable.
- Another site could frame the game and capture key presses (clickjacking).
- Browsers could guess (sniff) content types.

**Root cause:** Flask sends no security headers by default, and none were added.

**Evidence:** `test_security_headers_are_set` failed on all three paths.

**AI assistance:** the blind review found it (#5). The missing CSP was already known.

**Remediation:**

- **Requirement:** "Every response must tell the browser to run only this site's scripts, to
  refuse framing, not to guess content types and not to leak the URL in the referrer. The game
  must keep working, including Pyodide's WebAssembly."
- **Change (`b22af65`):**
  - `after_request` sets the CSP (`app.CSP` plus `frame-ancestors 'none'`), `nosniff`,
    `X-Frame-Options: DENY` and `Referrer-Policy: no-referrer`.
  - HSTS is sent only over HTTPS.
  - A test keeps the template's `<meta>` CSP equal to `app.CSP`.

**Verification:**

- The tests pass.
- `csp-check.mjs`: an injected inline `<script>` and an `onerror` handler did **not** run, and
  framing from another origin was refused with a `frame-ancestors` violation.

**Regression impact:** none (browser replay: no CSP violations in either mode).

---

## Finding SEC-06: Weak `SECRET_KEY` values accepted

**Severity:** Low

**Location:** `config.py` `load_config()`

**Description:** only an empty key and `change-me` were refused, so `abc` would start the
server.

**Security impact:** a short or guessable key can be brute-forced. Anyone who knows it can
sign their own session cookies with any `run_id`.

**Root cause:** the check only blocked the placeholder, not weak values in general.

**Evidence:** `test_weak_secret_keys_are_refused` with `short` and 31 × `a`: **no error** on
the original code.

**AI assistance:** the blind review found it (#6) and suggested a minimum of 32 bytes.

**Remediation:**

- **Requirement:** "The server must refuse to start unless `SECRET_KEY` is at least 32
  characters and isn't the placeholder."
- **Change (`38cac8f`):** `MIN_KEY_LENGTH = 32` and a clearer error message. `.env.example`
  already suggests `secrets.token_hex(32)`, which gives 64 characters.

**Verification:** the tests pass, and a 64-character key is accepted.

**Regression impact:** an existing `.env` with a short key must be regenerated.

---

## Finding SEC-07: Weak dependency pinning; development server only

**Severity:** Low

**Location:**

- `requirements.txt`
- `README.md`

**Description:**

- Only Flask, python-dotenv and pytest were pinned. Werkzeug, Jinja2, itsdangerous,
  MarkupSafe, click and blinker were whatever pip resolved, with no hashes.
- pytest was installed on the server.
- Only `flask run` (the Werkzeug development server) was documented.

**Security impact:**

- A later install could pull a newly vulnerable or compromised release.
- Builds couldn't be reproduced exactly.
- The development server is unsafe to expose, and so is its debugger if `FLASK_DEBUG=1`.

**Root cause:** `requirements.txt` was written by hand for the direct dependencies, and
deployment was out of scope for Part 1.

**Evidence:**

- `test_runtime_requirements_are_fully_pinned_with_hashes` failed.
- `pip freeze` showed unpinned indirect packages installed.

**AI assistance:**

- The blind review found it (#7).
- The follow-up dependency review found the mixed dev dependencies.
- During the fix, the AI noticed that `colorama` (Windows only) would be missing from a lock
  file built on Linux, and used `uv --universal` to keep it.

**Remediation:**

- **Requirement:** "Every package, direct or indirect, must be pinned to an exact version and
  checked by hash. Test tools must not be installed on the server. The README must say how to
  run the server safely in production."
- **Change (`9cbe788`):**
  - `requirements.in` and `requirements-dev.in` are the inputs, compiled with
    `uv pip compile --universal --generate-hashes`.
  - `requirements.txt` has 8 runtime packages; `requirements-dev.txt` has 20, including
    pytest and bandit.
  - README: installing with `--require-hashes`, and a new "Deploying server mode" section.

**Verification:**

- Clean virtual environments installed both files with `--require-hashes`.
- The runtime one contains no pytest.
- 240 tests pass from the dev environment.
- `pip-audit` finds no known vulnerabilities in either file.

**Regression impact:** the install command changes (README updated).

---

## Finding SEC-08: CSRF defence relied on one control

**Severity:** Info

**Location:** `app.py` `require_json_posts()`

**Description:** the only defence against cross-site requests was the rule that POST bodies
must be `application/json`. A cross-site form can't send that type without a CORS preflight,
which the app never approves.

**Security impact:** none today. At most, a cross-site request could reset a player's run. But
if CORS were ever added, the protection would disappear silently.

**Root cause:** the design relied on a side effect of the content-type rule (PRD §9 left
SameSite or a token for Part 2).

**Evidence:** `test_cross_site_posts_are_refused`: a POST with `Origin: https://evil.example`
got **200**.

**AI assistance:** the blind review found it (#8) and suggested SameSite cookies plus an
`Origin` check.

**Remediation:**

- **Requirement:** "A POST that a browser marks as coming from another site must be refused,
  independently of the content-type rule. Same-site requests and tools that send no `Origin`
  must still work."
- **Change (`ff3c6b7`):** `require_same_origin_posts()` returns 403 if `Origin` is present and
  its host isn't `request.host` (this includes `Origin: null`). Combined with
  `SameSite=Strict` (SEC-04), there are now three separate layers.

**Verification:** the test passes: another origin, `null` and a look-alike
`localhost.evil.example` get 403; same-origin and no `Origin` get 200. In the browser, all API
calls returned 200.

**Regression impact:** none. Behind a proxy that changes the host, `ProxyFix` is needed
(README).

---

## Finding SEC-09: Raw error text shown to the player

**Severity:** Low

**Location:** `static/js/main.js`, the `main().catch(...)` handler

**Description:** on a load failure, the page showed `"Failed to load: " + e`, the raw
exception text.

**Security impact:** it reveals internal detail (URLs, file names, exception types) to anyone,
which helps an attacker map the app. It's also poor practice for production (the brief's
Part 9).

**Root cause:** a debugging convenience from development was left in.

**Evidence:** `test_load_errors_are_not_shown_raw_to_the_player` matched the concatenation.

**AI assistance:** known before the review began (CLAUDE.md, "findings already known"). **The
blind review missed it.**

**Remediation:**

- **Requirement:** "When loading fails, the player must see a fixed, friendly message. The
  details go only to the developer console."
- **Change (`9e0bf5e`):** the message is now "The game failed to load. Please reload the
  page."; `console.error(e)` is unchanged.

**Verification:** the test passes. `loadfail.mjs` blocked `engine/game.zip`; both modes showed
the fixed message, and the console still had the details.

**Regression impact:** none.

---

## Finding SEC-10: The build follows symlinks

**Severity:** Low

**Location:**

- `scripts/build_static.py` `build()`
- `scripts/bundle_engine.py` `make_zip()`

**Description:** `shutil.copytree`, `copy2` and `Path.glob` follow symlinks. A link such as
`static/x.txt → ../.env` would copy the target file's real contents into `docs/`, which GitHub
Pages publishes, or into `engine/game.zip`, which anyone can download.

**Security impact:** a mistaken or malicious symlink would publish secrets. It needs write
access to the repo, and no symlink exists today.

**Root cause:** the build scripts trusted the source tree, and Python's copy functions follow
links by default.

**Evidence:**

- In a scratch folder, a symlink to a fake `.env` was copied as its contents.
- `test_the_build_refuses_symlinks` failed (the build completed).

**AI assistance:** found by the follow-up path review, which looked beyond runtime routes to
the build scripts. **The blind review missed it.**

**Remediation:**

- **Requirement:** "The build must never publish a file through a symlink. If one exists in a
  published folder, stop with an error before anything is copied or deleted."
- **Change (`c4cef54`):** `refuse_symlinks()` checks `templates/`, `static/` and `levels/`
  before `build()` deletes or copies anything, and `game/` before zipping. The server builds
  its zip with the same function.

**Verification:** the test passes. A symlink in `static/` and one in `game/` each raise
`ValueError: refusing to publish a symlink`.

**Regression impact:** none (the repo has no symlinks; `docs/` was rebuilt and is identical).

---

## Finding SEC-11: The static build doesn't escape HTML in its template (latent)

**Severity:** Info

**Location:** `scripts/build_static.py` (originally `Template(...).render(mode="static")`)

**Description:** a bare `jinja2.Template` doesn't escape HTML, unlike Flask's
`render_template`.

**Security impact:** none today, because the only value is the constant `"static"`. If the
build ever inserted level data (level names may contain `<`), it would put unescaped markup
into the public site, i.e. stored XSS.

**Root cause:** the build reused Jinja directly, without Flask's escaping setting.

**Evidence:**

- Found by reading the code.
- `test_static_build_template_escapes_values` failed (with `ImportError`: the helper it calls
  didn't exist before the fix).

**AI assistance:** found by the follow-up XSS review. **The blind review and bandit both
missed it** (bandit's B701 only checks `Environment(...)`).

**Remediation:**

- **Requirement:** "Both modes must escape every value inserted into the page template."
- **Change (`4d5323a`):** `render_page(mode)` uses `Environment(autoescape=True)`.

**Verification:** the test passes. `"><script>` is rendered as `&lt;script&gt;`.

**Regression impact:** none (the built page is byte-for-byte unchanged).

---

## Finding SEC-12: Local paths in early git history (accepted risk)

**Severity:** Info

**Location:** compiled `game/__pycache__/*.pyc` in commits `51c93d1` and `81e4a0d`

**Description:** compiled Python files contain the absolute path of the source file, which
includes the local username and folder layout.

**Security impact:** minor information disclosure. No credentials are involved.

**Root cause:** `__pycache__/` was committed before it was added to `.gitignore`.

**Evidence:** the masked secret scan of all 60 blobs in the history.

**AI assistance:** found by the follow-up secrets review (a long random-looking string turned
out to be a file path).

**Remediation:** none. The files are no longer tracked. Removing them from history would mean
rewriting pushed commits and moving the `v1-original` tag, the Part 1 submission marker. The
risk is too small to justify that.

**Verification:** `git ls-files | grep __pycache__` finds nothing.

**Regression impact:** none.
