# AUTH_MIDDLEWARE Security Report

## Status: MEDIUM (fixed)

## Findings

Routes (all in `src/app.py`):

| Route | Methods | Protection |
|---|---|---|
| `/` | GET, POST | HTTP Basic auth in production, via `before_request` |
| `/health` | GET | Deliberately unauthenticated; returns only `{"status": "ok"}` |
| `/static/<path>` | GET | Same `before_request` hook, so authenticated in production |

Auth runs in a global `before_request` hook, before any handler, with constant-time comparison.

- **MEDIUM — fail-open environment detection.** `is_production()` returned true only when `APP_ENV=production` or `RAILWAY_ENVIRONMENT` was set. On any other host, forgetting `APP_ENV` served the whole app with no authentication:
  ```python
  return os.getenv("APP_ENV", "").strip().lower() == "production" or bool(os.getenv("RAILWAY_ENVIRONMENT"))
  ```
- **LOW — non-ASCII credentials caused a 500.** `hmac.compare_digest` raises `TypeError` on non-ASCII `str`, so `Authorization: Basic` with a non-ASCII username or password produced an unhandled exception instead of a 401. Not a bypass.
- The username and password comparisons were joined with `and`, which skips the password comparison when the username is wrong. Negligible, tidied while there.

## What's at risk

With auth off on a public host, anyone could use the server as a fetch proxy and spend the owner's OpenAI budget through the analyse action.

## What's already secure

Global hook, `/health` exemption limited to one path, 503 when credentials are missing or too short (password under 16, secret key under 32), `WWW-Authenticate` challenge on 401.

## Recommendations

1. Require auth unless `APP_ENV=development` is set explicitly (done).
2. Compare credentials as UTF-8 bytes (done).
