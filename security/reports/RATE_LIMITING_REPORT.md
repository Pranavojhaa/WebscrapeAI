# RATE_LIMITING Security Report

## Status: LOW (fixed 2026-10-15; Railway client-address handling unverified)

## Findings

Originally there was no rate limiting. There are no login, registration or password-reset endpoints; authentication is HTTP Basic on every request.

- Password guessing was unthrottled. A 16-character minimum made online guessing impractical for a random password, but not for a weak human-chosen one.
- The expensive actions (outbound fetch, OpenAI analysis) were limited only by authentication.

Fixed in `src/app.py` with an in-memory sliding-window limiter, keyed per client address (IPv6 per /64):

| Limit | Applies to | Response |
|---|---|---|
| 10 per 15 minutes | Failed Basic-auth attempts (production only). Once reached, even the right password gets 429 until the window passes. The browser's first request without credentials is not counted. | 429 + `Retry-After` |
| 30 per minute | Every POST to `/` with a valid CSRF token | 429 + `Retry-After` |
| 20 per hour | POSTs with `action=analyze` (OpenAI calls) | 429 + `Retry-After` |

Client address:
- On Railway (`RAILWAY_ENVIRONMENT` set), `ProxyFix(x_for=1)` takes the last `X-Forwarded-For` entry, the one Railway's proxy appends. A client-supplied header lands to the left of it and is ignored.
- Everywhere else `REMOTE_ADDR` is used and `X-Forwarded-For` is ignored entirely (tested).
- If Railway turns out to add more than one proxy hop, the last entry is a Railway address. Everyone then shares one bucket: the limits become too strict, but they cannot be bypassed.

## What's at risk

Remaining: the counters live in each Gunicorn worker (2 in `railway.json`), so the effective ceiling is up to double and resets on restart or deploy. An attacker with many IPv4 addresses gets a separate budget per address.

## What's already secure

Minimum credential lengths; constant-time comparison; 32 KB request cap; 5 MB and 30 s fetch caps; OpenAI output capped at 500 tokens with one retry.

## Recommendations

1. After deploying, confirm two different clients get separate limits (see the plan).
2. Set a spend limit on the OpenAI key.
3. If traffic grows, move to Flask-Limiter with a shared Redis store, or a limiter at the edge.
