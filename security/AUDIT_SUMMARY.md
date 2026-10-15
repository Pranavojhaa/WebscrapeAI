# Security Audit Summary

Date: 2026-10-13
Branch: `security-review` (changes uncommitted)
Target scanned: local dev server at `http://127.0.0.1:5057`. No deployed URL was scanned, so host-level results (HSTS delivery, edge headers, CORS added by the host) are unverified.

## Architecture change: 2026-10-15

This audit predates the account-based deployment work on `shippy/github-deployment-2026-10-13`. The app now has a separate public cache-only demo and a private account-based service with PostgreSQL storage, session login, admin-managed accounts, and isolated Render environments. Render network isolation requires a Pro workspace; the current always-on configuration is estimated at about $45/month before storage, bandwidth overages, and tax. Relevant category reports and plans have been revised, but the historical scan totals below are not a current release sign-off. No Render services or database have been provisioned; authentication, database reachability, proxy headers, cookies, rate limits, and billing remain to be verified before deployment.

The public demo bundles ten snapshots captured from the selected public pages on 2026-10-15. It displays captured full-page element counts and curated headings, related links, and summaries. It does not make network requests, invoke the scraper, or call AI at runtime; snapshots can become stale as source pages change.

Local deployment-branch verification on 2026-10-15: 58 tests passed and one scheduled browser-integration test was skipped; Ruff, byte-compilation, all three dependency audits, YAML parsing, and `git diff --check` passed. These checks do not substitute for a remote CI run on this unpushed branch or live Render verification.

The prior table and findings are retained as the historical `security-review` audit baseline; do not apply its N/A statuses or single-credential conclusions to the current deployment branch.

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
- Non-ASCII CSRF tokens return 400 rather than causing a 500.
- CSP gains `object-src 'none'`; `X-Frame-Options: DENY` added; HSTS sent in production.
- Scraped links render as anchors only for http(s); CSV and XLSX exports neutralize formula cells.
- Library exception text no longer reaches the page.
- `.env.example` added.

Follow-up on 2026-10-15:

- Rate limiting: per-client limits on failed logins (10 per 15 min), form posts (30 per min) and AI analysis (20 per hour), returning 429.
- Lock files: `requirements.txt` and `requirements-selenium.txt` are now hashed, fully pinned locks generated from `.in` files; all 52 pinned versions are clear in OSV.
- Selenium: rendering requires `APP_ENV=development` explicitly, matching the fail-closed auth.

Tests: historical; run the current deployment branch suite before treating this audit as release validation.

## Still open

- Rate limits are per Gunicorn worker and in memory, so limits multiply across workers and reset on deploy. Client identity behind the selected host's proxy remains unverified until deployment.
- Selenium has no per-request address checks inside the browser; it is now development-only. Running it in production would need a filtering egress proxy.
- GitHub Actions has not been confirmed for the current unpushed branch; local verification passed.

## Tools not run

- `gitleaks`: not installed (`brew install gitleaks`). History was checked by regex only.
- `pip-audit` passed for the runtime, Selenium, and public-demo lock files on 2026-10-15.
- `semgrep`: not installed (`brew install semgrep`).

## Remaining manual verification

- Run `python3 ~/.claude/skills/vibe-check/scripts/check.py <deployed-url>` after deploying; confirm HSTS, the `Server` header, CORS and the `Secure` cookie flag.
- Confirm the private app URL shows account login and `/health` returns 200.
- Start local runs with `APP_ENV=development`; without it the app now returns 503.
- Set an OpenAI usage limit and use unique administrator/member passwords.
- Decide whether formula neutralization in exports is acceptable for your data.
- After deploying, check that two different networks get separate rate limits (see `plans/RATE_LIMITING_PLAN.md`).
