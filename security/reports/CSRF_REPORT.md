# CSRF Security Report

## Status: LOW (fixed)

## Findings

- Session cookie: `HttpOnly`, `SameSite=Lax`, and `Secure` in production. Confirmed on the live response (`Secure` is absent locally by design).
- Every POST is checked in `before_request` against a per-session token (`secrets.token_urlsafe(32)`), compared in constant time. Live: POST without a token returns 400.
- No GET route changes state.
- **LOW — non-ASCII token caused a 500.** `hmac.compare_digest(supplied_token, expected_token)` raised `TypeError` when the submitted token contained a non-ASCII character. Reproduced live: `csrf_token=é` returned 500. Not a bypass, but an unhandled exception any visitor could trigger.

## What's at risk

No forgery was possible. The crash produced stack traces in logs on demand.

## What's already secure

Token plus `SameSite=Lax`; both forms in the template carry the token; check runs before any handler.

## Recommendations

1. Compare as UTF-8 bytes (done).
