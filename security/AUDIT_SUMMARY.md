# Security Audit Summary

Date: 2026-10-13
Branch: `security-review` (changes uncommitted)
Target scanned: local dev server at `http://127.0.0.1:5057`. No deployed URL was scanned, so host-level results (HSTS delivery, edge headers, CORS added by the host) are unverified.

## Results

| # | Category | Status | Report | Plan |
|---|----------|--------|--------|------|
| 1 | SECRETS_EXPOSURE | LOW (fixed) | [report](reports/SECRETS_EXPOSURE_REPORT.md) | [plan](plans/SECRETS_EXPOSURE_PLAN.md) |
| 2 | DATABASE_ACCESS | N/A | [report](reports/DATABASE_ACCESS_REPORT.md) | [plan](plans/DATABASE_ACCESS_PLAN.md) |
| 3 | AUTH_MIDDLEWARE | MEDIUM (fixed) | [report](reports/AUTH_MIDDLEWARE_REPORT.md) | [plan](plans/AUTH_MIDDLEWARE_PLAN.md) |
| 4 | ACCESS_CONTROL | N/A | [report](reports/ACCESS_CONTROL_REPORT.md) | [plan](plans/ACCESS_CONTROL_PLAN.md) |
| 5 | FRONTEND_SECRETS | PASS | [report](reports/FRONTEND_SECRETS_REPORT.md) | [plan](plans/FRONTEND_SECRETS_PLAN.md) |
| 6 | SSRF | MEDIUM (fixed) | [report](reports/SSRF_REPORT.md) | [plan](plans/SSRF_PLAN.md) |
| 7 | CSRF | LOW (fixed) | [report](reports/CSRF_REPORT.md) | [plan](plans/CSRF_PLAN.md) |
| 8 | SECURITY_HEADERS | MEDIUM (fixed locally) | [report](reports/SECURITY_HEADERS_REPORT.md) | [plan](plans/SECURITY_HEADERS_PLAN.md) |
| 9 | CORS | PASS (local only) | [report](reports/CORS_REPORT.md) | [plan](plans/CORS_PLAN.md) |
| 10 | RATE_LIMITING | LOW (fixed) | [report](reports/RATE_LIMITING_REPORT.md) | [plan](plans/RATE_LIMITING_PLAN.md) |
| 11 | SQL_INJECTION | N/A | [report](reports/SQL_INJECTION_REPORT.md) | [plan](plans/SQL_INJECTION_PLAN.md) |
| 12 | XSS | LOW (fixed) | [report](reports/XSS_REPORT.md) | [plan](plans/XSS_PLAN.md) |
| 13 | PAYMENT_WEBHOOKS | N/A | [report](reports/PAYMENT_WEBHOOKS_REPORT.md) | [plan](plans/PAYMENT_WEBHOOKS_PLAN.md) |
| 14 | FILE_UPLOADS | N/A | [report](reports/FILE_UPLOADS_REPORT.md) | [plan](plans/FILE_UPLOADS_PLAN.md) |
| 15 | ERROR_HANDLING | LOW (fixed) | [report](reports/ERROR_HANDLING_REPORT.md) | [plan](plans/ERROR_HANDLING_PLAN.md) |
| 16 | PASSWORD_HASHING | N/A | [report](reports/PASSWORD_HASHING_REPORT.md) | [plan](plans/PASSWORD_HASHING_PLAN.md) |
| 17 | DEPENDENCIES | PASS (fixed) | [report](reports/DEPENDENCIES_REPORT.md) | [plan](plans/DEPENDENCIES_PLAN.md) |

## Live scan, before and after

| | PASS | FAIL | WARN | INFO |
|---|---|---|---|---|
| Before | 16 | 1 | 2 | 2 |
| After | 18 | 0 | 1 | 2 |

The remaining WARN is the `Server: Werkzeug/... Python/...` header from the Flask development server, which production does not use.

## Critical issues

None.

## What was fixed

- Authentication now fails closed: required unless `APP_ENV=development`.
- DNS rebinding closed: the address that is checked is the address connected to.
- Total fetch time capped at 30 seconds.
- Non-ASCII CSRF token or Basic credentials return 400/401 where they caused a 500.
- CSP gains `object-src 'none'`; `X-Frame-Options: DENY` added; HSTS sent in production.
- Scraped links render as anchors only for http(s); CSV and XLSX exports neutralize formula cells.
- Library exception text no longer reaches the page.
- `.env.example` added.

Follow-up on 2026-10-15:

- Rate limiting: per-client limits on failed logins (10 per 15 min), form posts (30 per min) and AI analysis (20 per hour), returning 429.
- Lock files: `requirements.txt` and `requirements-selenium.txt` are now hashed, fully pinned locks generated from `.in` files; all 52 pinned versions are clear in OSV.
- Selenium: rendering requires `APP_ENV=development` explicitly, matching the fail-closed auth.

Tests: `tests/test_security.py` adds 14 regression tests, all passing. The full suite runs 46 tests with 1 error and 1 skip; the error is `test_analyzer.AnalyzerTests.test_cli_chat_sends_each_question_once`, which failed the same way before these changes because it needs `OPENAI_API_KEY` in the environment.

## Still open

- Rate limits are per Gunicorn worker and in memory, so the ceiling is up to 2x and resets on deploy. Whether Railway's `X-Forwarded-For` gives each client its own bucket is unverified until deployed.
- Selenium has no per-request address checks inside the browser; it is now development-only. Running it in production would need a filtering egress proxy.
- CI has not run against the new lock files.

## Tools not run

- `gitleaks`: not installed (`brew install gitleaks`). History was checked by regex only.
- `pip-audit`: not installed locally. Installed packages were checked against OSV directly.
- `semgrep`: not installed (`brew install semgrep`).

## Remaining manual verification

- Run `python3 ~/.claude/skills/vibe-check/scripts/check.py <railway-url>` after deploying; confirm HSTS, the `Server` header, CORS and the `Secure` cookie flag.
- Confirm the Railway URL prompts for credentials and `/health` returns 200.
- Start local runs with `APP_ENV=development`; without it the app now returns 503.
- Set an OpenAI usage limit and use a randomly generated `APP_PASSWORD`.
- Decide whether formula neutralization in exports is acceptable for your data.
- After deploying, check that two different networks get separate rate limits (see `plans/RATE_LIMITING_PLAN.md`).
