# Part 12: Automated Security Testing

**Tool:** bandit 1.9.4, a static analyser for Python (SAST).

**Scope:** `app.py config.py db.py game scripts`, 555 lines before the fixes and 634 after.

**Runs:**

- Before fixes, at tag `v2-pre-review`: `security/evidence/bandit-before.txt`.
- After all Part 14 fixes, on branch `hardening`: `security/evidence/bandit-after.txt`.

**Command:** `bandit -r app.py config.py db.py game scripts`. Bandit is installed from
`requirements-dev.txt`.

## Results

| Run | High | Medium | Low | Findings |
|---|---|---|---|---|
| Application code, before | 0 | 0 | 1 | B101 `assert` at `game/engine.py:27` |
| Application code, after | 0 | 0 | 1 | The same B101 (not a vulnerability, see below) |
| `tests/`, after (run for completeness) | 0 | 0 | 208 | 206 × B101 `assert`, 2 × B105 "hardcoded password" |

## Triage

| Finding | Applies? | Classification | Reasoning |
|---|---|---|---|
| B101 `assert MAX_FALL * DT < TILE` (`game/engine.py:27`) | No | False positive | Python's `-O` flag removes asserts, so bandit warns about them. This assert checks two **constants** when the module is imported. It doesn't check untrusted input or enforce access control, so removing it can't let an attacker past anything. It guards a physics design rule (no tunnelling through floors), which `pytest` also enforces. Not changed. |
| B101 × 206 in `tests/` | No | False positive | pytest is built on `assert`, and tests are never run with `-O`. |
| B105 `"SECRET_KEY": "test"` (`tests/conftest.py:30`, `tests/test_security.py:246`) | No | False positive | Dummy keys used only by the tests. The real key comes from the environment, and since SEC-06 it must be at least 32 characters. |

## What bandit did not find

Bandit reported no issues of any substance. The real problems in this codebase were found by
manual review, the AI reviews and tests (see `findings.md`). Examples:

- **SEC-11:** bandit's B701 check looks for `jinja2.Environment(autoescape=False)`. It did not
  flag the bare `jinja2.Template(...)` in `build_static.py`, which also doesn't escape.
- **SEC-01, SEC-02, SEC-04 and SEC-08:** these are business-logic and configuration flaws (a
  client-reported time, unbounded tables, Flask cookie defaults, a single CSRF control). A
  pattern-matching scanner has nothing to match against.
- **SEC-03 and SEC-07:** these are in HTML and `requirements.txt`, which bandit doesn't read.
  `pip-audit` (`evidence/pip-audit-after.txt`) covers known-vulnerable packages, but no tool
  flagged "only the top-level packages are pinned".
- **Verified controls:** bandit reported no SQL injection (B608) because every query uses `?`
  placeholders. This matches the manual injection tests in `findings.md`.

**Conclusion:** treat the tool's output as evidence, not a verdict. A clean bandit run showed
that the code avoids the patterns bandit knows about. It didn't show the app was secure.
