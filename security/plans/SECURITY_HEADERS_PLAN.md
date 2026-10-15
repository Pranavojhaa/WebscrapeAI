# SECURITY_HEADERS Fix Plan

## Changes

- `src/app.py` — `add_security_headers` adds `object-src 'none'`, `X-Frame-Options: DENY`, and HSTS when `is_production()`.

## New files

- `tests/test_security.py` — `test_security_headers`.

## Verification goals

- [x] CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy present on HTML and static responses (live, local)
- [x] HSTS present in production mode (test)
- [x] CSP declares `default-src`, `object-src 'none'`, `base-uri`, `form-action`, `frame-ancestors`; no unsafe script sources
- [x] Page renders with the CSP enforced (no inline script or style in the template)
- [ ] All five headers present on the deployed app (not checked)

## Manual verification (for the human)

- Run the scanner against the Railway URL. Local results cannot show what Railway's edge adds or strips.
- Only add `preload` if every subdomain is HTTPS-only.
