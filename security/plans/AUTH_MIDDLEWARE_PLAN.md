# AUTH_MIDDLEWARE Fix Plan

## Changes

- `src/app.py` — replaced shared HTTP Basic credentials with private-mode sessions, CSRF-protected login/logout, active-account checks, and admin-only account management.
- `src/account_store.py` — added SQLite local testing and PostgreSQL production storage with hashed passwords.
- `src/demo_app.py` — separated the public cache-only demo from private scraping and AI routes.
- `render.yaml` — separated demo and private environments and enabled network isolation.

## Verification goals

- [x] Missing production database or app secret fails closed.
- [x] Unauthenticated production requests redirect to `/login`.
- [x] Inactive users cannot access private routes.
- [x] Login, logout, and account changes require CSRF tokens.
- [x] Non-admin accounts cannot access user administration.
- [ ] Verify authentication and proxy/cookie behavior on Render staging.

## Manual verification

- Keep the private service internet-reachable for approved users, but protect app routes with account login.
- Confirm the demo URL cannot reach private service routes, credentials, or the database.
