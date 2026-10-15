# RATE_LIMITING Security Report

## Status: LOW (implemented; hosted client-address behavior unverified)

## Findings

The app uses in-memory sliding-window limits keyed by authenticated account after login or by source address before login. IPv6 clients are grouped per /64.

| Limit | Applies to | Response |
|---|---|---|
| 10 per 15 minutes | Failed private-app login attempts per source/email key | 429 + `Retry-After` |
| 30 per minute | POST requests with a valid CSRF token | 429 + `Retry-After` |
| 20 per hour | POST requests with `action=analyze` | 429 + `Retry-After` |

The demo only serves static bundled examples and has no scrape, AI, login, or database endpoint.

## What's at risk

Counters are in-memory per Gunicorn worker, multiply across replicas, and reset on restart or deploy. Render's client IP/proxy chain remains unverified until staging is online. An attacker with multiple addresses can obtain separate IP-based budgets before authentication.

## What's already secure

- Failed login attempts are throttled per source address and normalized email.
- POST requests require CSRF validation before limits or route handling.
- The demo's form selects only one of ten fixed fixtures; it cannot trigger outbound requests or AI usage.

## Recommendations

1. Verify separate-client rate limits and `REMOTE_ADDR` behavior on staging before changing `TRUSTED_PROXY_HOPS`.
2. Set an OpenAI spend limit on the private API key.
3. Use a shared limiter before adding replicas or expanding access.
