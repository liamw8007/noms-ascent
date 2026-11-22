# Part 16: Before-and-After Security Assessment

| Version | Tag / branch | Commit |
|---|---|---|
| **Original** | tag `v2-pre-review` | `9d927b4` |
| **Hardened** | branch `hardening` | fixes in `5ecc59e` … `9cbe788` |

Both versions run the same game in both modes.

| Area | Original | Security issue | Remediation | Result |
|---|---|---|---|---|
| Game-state trust | The server accepted the completion time the client reported | A script could post every level, with every pellet, at `min_time` the moment a run started, and top the leaderboard (SEC-01) | The server times each level itself and rejects reports faster than its own clock | **Improved.** Instant fake runs are rejected. A patient script that waits out real time is still possible (accepted limitation). |
| Input validation | Already strict: types, ranges, pellet IDs, `NAME_RE`, 4 KB limit, JSON only | None found. Over 60 invalid-input cases were tested | Kept. Test coverage extended (`test_security.py`) | **Verified control** |
| Resource limits | `runs` gained a row per request; `scores` grew forever | An anonymous flood fills the disk; "database is locked" errors (SEC-02) | Active-run cap (503 when full), top 100 scores kept, WAL mode; per-IP limits at the proxy | **Improved** |
| Third-party code | Pyodide 0.27.2 (Jan 2025) from jsDelivr: no SRI, no CSP | A compromised CDN would run its own code on the page with the player's cookie; outdated runtime (SEC-03) | Pyodide 314.0.8 hosted by the site (tarball integrity checked); CSP allows `'self'` only | **Improved.** No requests to other sites, and the game works offline. |
| Browser hardening | No security headers | No second layer against XSS; the game could be framed (clickjacking); MIME sniffing (SEC-05) | CSP (`frame-ancestors 'none'`), `nosniff`, `X-Frame-Options`, `Referrer-Policy`, HSTS over HTTPS | **Improved.** An injected script and a cross-origin frame were both blocked in the browser. |
| XSS | `textContent` in the score table; names checked by `NAME_RE` | None exploitable; the static build template wasn't escaped (latent, SEC-11) | Autoescaping in `build_static.py`; CSP as a second layer | **Improved** (it was already a verified control) |
| Sessions and cookies | Flask defaults: no `Secure`, no `SameSite`, no lifetime | A sniffed cookie (over HTTP) takes over the player's run (SEC-04) | `Secure`, `HttpOnly`, `SameSite=Strict`, 24 h lifetime | **Improved** |
| CSRF | Only the `application/json` check | One control; it would fail silently if CORS were ever added (SEC-08) | `Origin` check on POSTs plus `SameSite=Strict` | **Improved.** Three separate layers. |
| Secrets and configuration | Any non-empty, non-placeholder `SECRET_KEY` accepted | A guessable key lets anyone forge cookies (SEC-06) | Minimum 32 characters | **Improved** |
| Error handling | Generic JSON errors on the server, but raw exception text on the page | Internal detail shown to the player on a load failure (SEC-09) | A fixed message on the page; details in the console | **Improved** |
| Dependencies | Direct dependencies pinned; indirect ones unpinned; no hashes; pytest mixed in | A future install could pull a different or compromised version (SEC-07) | Hash-pinned lock files for every package (`uv --universal`), `requirements-dev.txt`, pip-audit clean | **Improved** |
| Deployment configuration | Only `flask run` documented; debug off by default | The development server and its debugger are unsafe to expose (SEC-07) | README "Deploying server mode": WSGI server, HTTPS, proxy rate limits, `FLASK_DEBUG=0` | **Improved** (documented) |
| Build pipeline | The build followed symlinks | A stray symlink would publish its target (e.g. `.env`) to GitHub Pages (SEC-10) | The build refuses symlinks | **Improved** |
| SQL injection | `?` placeholders everywhere | None: payloads sent straight to `db.py` were stored as text | Kept | **Verified control** |
| Path traversal | `safe_join`; levels picked by index; no route serves `.py` files | None: traversal attempts returned 404 | Kept; build symlinks fixed (above) | **Verified control** |
| Git history | `.pyc` files with local paths in early commits | Reveals the local username and folder layout (SEC-12) | None: a history rewrite would change the pushed `v1-original` tag | **Accepted risk** |

## In numbers

| | Original | Hardened |
|---|---|---|
| Open findings (High / Medium / Low / Info) | 1 / 3 / 5 / 3 | 0 / 0 / 0 / 1 accepted (SEC-12) |
| Security tests | 19 API test functions (`test_api.py`) | plus 98 test cases in `test_security.py` (240 tests in total, all passing) |
| Third-party origins contacted by the page | 1 (`cdn.jsdelivr.net`) | 0 |
| Security response headers | 0 | 5 (6 over HTTPS) |
| Packages pinned with hashes | 0 of 8 | 8 of 8 runtime, 20 of 20 dev |
| bandit (High / Medium / Low) | 0 / 0 / 1 | 0 / 0 / 1 (the same false positive) |
