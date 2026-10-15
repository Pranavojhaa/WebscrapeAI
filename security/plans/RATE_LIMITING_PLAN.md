# RATE_LIMITING Fix Plan

## Changes

- `src/app.py` — `SlidingWindowLimiter` (stdlib, thread-safe, stale keys swept past 10,000 entries); `auth_failure_limiter`, `post_limiter`, `analysis_limiter`; `client_key()` groups IPv6 per /64; limits enforced in `before_request`; `ProxyFix` trusts only the explicitly configured `TRUSTED_PROXY_HOPS` count.
- `tests/test_app.py` — `setUp` clears the limiters so tests cannot trip each other.
- `README.md` — deployment step 2 describes the limits and their per-worker ceiling.

## New files

- `tests/test_security.py` — `test_form_posts_are_rate_limited_per_client`, `test_spoofed_forwarded_for_does_not_change_the_key_without_trusted_proxy`, `test_ai_analysis_has_its_own_tighter_limit`, `test_failed_logins_are_throttled_even_for_the_right_password`, `test_ipv6_clients_share_a_limit_per_64`.

## Verification goals

- [x] Failed authentication is throttled after 10 attempts in 15 minutes (test)
- [x] Throttled requests return 429 with `Retry-After` (test)
- [x] A spoofed `X-Forwarded-For` does not change the key without a trusted proxy (test)
- [x] Other clients are unaffected when one is limited (test)
- [x] Expensive AI analysis has a separate, tighter limit (test)
- [ ] Behind the selected host's proxy, the key is the real client address (needs a deployed check)

## Manual verification (for the human)

- After deploying, send 31 form posts from one network and confirm the 31st returns 429. Then submit a form from a different network (e.g. a phone on mobile data) and confirm it still succeeds. Verify the host's proxy-hop count before setting `TRUSTED_PROXY_HOPS`.
- Configure an OpenAI usage limit.
