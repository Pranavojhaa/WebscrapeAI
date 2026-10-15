# AUTH_MIDDLEWARE Fix Plan

## Changes

- `src/app.py` — `is_production()` now returns true unless `APP_ENV=development`; new `secrets_match()` compares UTF-8 bytes and is used for both credentials (joined with `&`).
- `README.md` — deployment paragraph updated to describe the fail-closed behaviour.

## New files

- `tests/test_security.py` — `test_unset_app_env_fails_closed`, `test_non_ascii_basic_auth_is_rejected_not_crashed`.

## Verification goals

- [x] With no `APP_ENV`, `/` returns 503 until credentials are configured (test)
- [x] Unauthenticated request in production returns 401 (existing test)
- [x] Non-ASCII Basic credentials return 401, not 500 (test)
- [x] Auth runs in `before_request`, before any handler
- [x] No admin routes exist

## Manual verification (for the human)

- **Behaviour change:** `python src/app.py` with no `APP_ENV` now returns 503. Use `APP_ENV=development python src/app.py`, as the README already says.
- After deploying, confirm the Railway URL prompts for credentials and `/health` returns 200.
