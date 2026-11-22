# Part 13: Security Test Suite

**Code:** `tests/test_security.py`, 98 test cases. Shared fixtures are in `tests/conftest.py`,
including a fake clock, so time-based rules can be tested without waiting.

**Running it:** `pytest` runs these tests with the rest of the suite: 240 tests in total, all
passing after the fixes.

**Evidence:** `security/evidence/pytest-before.txt` and `pytest-after.txt`.

## Method: red before, green after

Each finding was written as a test **before** its fix and marked `xfail(strict=True)`. On the
unfixed code, all 17 of these tests failed, which showed each problem was real
(`pytest-before.txt`):

- the server accepted the time a script reported;
- a 4th run was accepted;
- the cookie had no `Secure` flag;
- the headers were missing;
- a cross-site `Origin` was accepted;
- a short key was accepted;
- the error text was shown raw;
- the symlink was published;
- `requirements.txt` had no hashes.

Each fix commit removed its marker, so the same test now shows the fix works. A test marked
`strict` that unexpectedly passes counts as a failure, so a finding can't be marked "fixed"
while its test is still marked as expected to fail.

The browser can't be tested from pytest. The browser checks in `security/browser-check/` cover
it (see `regression.md`).

## Coverage by the brief's areas

| Area | What is tested | Tests |
|---|---|---|
| **Input validation** | Valid input; each missing field; empty bodies (`""`, `{}`, `null`, `[]`); wrong types for every field (strings, floats, bools, `null`, lists, objects); negative and zero values; huge values (`10^20`, `1e308`, `Infinity`, `NaN`, `1e999`, a 1,000-pellet list → 413); unexpected values (extra keys, another level's pellet, duplicates, SQL text, `{"$gt": 0}`); 15 bad names (types, length, `<script>`, `a'--`, non-ASCII, control characters); level numbers outside 1–3 | `test_valid_progress_is_accepted` … `test_level_numbers_outside_1_to_3_are_404` |
| **Game state** | Levels can't be skipped, repeated or extended past 3. The score is calculated by the server (`score`, `accepted_score` and `points` fields are rejected). `lives` from the client is rejected. A win can't be claimed without a level. A run is submitted once only. **SEC-01:** a level can't be finished faster than the server's clock, can't report more time than really passed, and each level is timed from when the previous one was accepted. **SEC-02:** the active-run cap, and only the top scores kept | `test_levels_cannot_be_skipped_…` … `test_only_the_top_scores_are_kept` |
| **Error handling** | 400, 404, 405, 413, 415 and 500 (from a forced exception and from a database that can't be opened) all return `{"error": "<generic name>"}` as JSON, with no traceback, file name, `.py`, Werkzeug or SQLite text | `test_errors_are_generic_json`, `test_an_unexpected_exception_is_a_generic_500`, `test_a_broken_database_is_a_generic_500` |
| **Browser output** | No HTML or code sinks (`innerHTML`, `document.write`, `eval`, `new Function`, string `setTimeout`) in any JS file. Names are inserted with `textContent`. A hostile name stored in the database comes back as JSON data unchanged. Server-mode and static-build templates escape values (**SEC-11**). A load failure doesn't show raw error text (**SEC-09**) | `test_javascript_has_no_html_or_code_sinks` … `test_load_errors_are_not_shown_raw_to_the_player` |
| **Configuration** | 4 KB body limit. Debug off by default. Weak `SECRET_KEY` values refused (**SEC-06**). Cookie is `Secure`, `HttpOnly`, `SameSite=Strict` and expires in 24 h (**SEC-04**). CSP, `nosniff`, `X-Frame-Options` and `Referrer-Policy` on every response, and the `<meta>` CSP matches the header (**SEC-05**). HSTS over HTTPS only. No third-party code on the page (**SEC-03**). Cross-site POSTs refused (**SEC-08**). Hash-pinned runtime requirements without pytest (**SEC-07**). The build refuses symlinks (**SEC-10**) | `test_request_bodies_are_limited_to_4_kb` … `test_the_build_refuses_symlinks` |

## Penetration-style checks run outside pytest

| Check | Tool | Result |
|---|---|---|
| A copied session cookie used from a second client | Flask test client | Before SEC-04 it took over the run, and that is still possible today (see `reports.md`, SEC-04). The fix limits how a cookie can be **stolen**. |
| Stored XSS: `<img onerror>`, `<script>` and `<svg onload>` names written straight into SQLite | Headless Chromium | Shown as text; no elements created, nothing ran |
| An injected inline script and `onerror` handler | Headless Chromium (`csp-check.mjs`) | Blocked by the CSP after SEC-05 |
| Framing the game from another origin | Headless Chromium (`csp-check.mjs`) | Refused by `frame-ancestors 'none'` |
| Path traversal (`../app.py`, `%2e%2e%2f.env`, …) | Flask test client | 404 |
| SQL injection sent straight into the `db.py` functions | Python | Stored as text; tables intact |
