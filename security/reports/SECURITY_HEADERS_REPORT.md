# SECURITY_HEADERS Security Report

## Status: MEDIUM (fixed locally; unverified on deploy)

## Findings

Headers are set by one global `after_request` hook in `src/app.py`. Host-level header configuration has not been set up.

Live scan before the fix:
- **FAIL** — CSP had no `object-src 'none'`: `default-src 'self'; style-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`
- **WARN** — `X-Frame-Options` absent (covered by `frame-ancestors` in modern browsers).
- **Missing** — `Strict-Transport-Security` was never set. The scanner skips HSTS on local targets, so this came from reading the code.

The rest of the CSP is sound: `default-src 'self'`, no `unsafe-inline` or `unsafe-eval`, explicit `base-uri`, `form-action`, `frame-ancestors`. The template has no inline scripts or styles, so the policy does not break the page.

## What's at risk

Low in practice, since the templates escape output. HSTS protects the first connection from downgrade interception; production authentication uses secure session cookies.

## What's already secure

`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, a real CSP on every response including static files.

## Recommendations

1. Add `object-src 'none'` (done).
2. Add `X-Frame-Options: DENY` (done).
3. Send HSTS in production (done: `max-age=31536000; includeSubDomains`). `preload` is optional and not added.
