# CSRF Fix Plan

## Changes

- `src/app.py` — CSRF comparison uses `secrets_match()`.

## New files

- `tests/test_security.py` — `test_non_ascii_csrf_token_is_rejected_not_crashed`.

## Verification goals

- [x] Session cookie has `HttpOnly` and `SameSite=Lax`; `Secure` in production
- [x] All POSTs validate a CSRF token
- [x] No GET route changes state
- [x] POST without a token returns 400 (live)
- [x] Non-ASCII token returns 400, was 500 (live and test)

## Manual verification (for the human)

- On the deployed app, check in DevTools that the `session` cookie shows `Secure`.
