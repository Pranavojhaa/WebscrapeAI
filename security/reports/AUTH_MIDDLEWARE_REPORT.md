# AUTH_MIDDLEWARE Security Report

## Status: Implemented; hosted verification pending

## Findings

| Route | Production behavior |
|---|---|
| `/` | Requires an active session; otherwise redirects to `/login` |
| `/login` | Public sign-in form; credentials are checked against the private account database |
| `/logout` | Requires a session and valid CSRF token; clears the session |
| `/admin/users` | Requires an active administrator account; others receive 404 |
| `/health` | Public; reports only status and configured app mode |
| `/static/<path>` | Public static assets; contains no account or API secrets |

Authentication is fail-closed: all environments except explicit `APP_ENV=development` require the private production configuration. The private service returns 503 if its app secret or Postgres URL is missing, or if the initial administrator cannot be bootstrapped.

Successful login clears the prior session before setting the account identity. Inactive accounts are denied on each protected request. Failed logins are throttled by source address and normalized email.

## What's at risk

- The app URL is publicly reachable; the login is enforced by the app, not the hosting edge.
- Rate limits are in-memory and per worker; they are not shared across replicas and reset on restart.
- No password-change or reset flow exists yet.
- Render proxy identity and hosted headers still require staging verification.

## What's already secure

- Production session cookies are HTTP-only, SameSite=Lax, and Secure.
- CSRF validation runs before every POST handler.
- The demo runs through `src.demo_app:app`, not the private app's auth bypass or scraper routes.
- Missing credentials fail closed; `/health` is the only unauthenticated private-app route besides sign-in and static files.

## Recommendations

1. Keep the private service as a public web service with app-level login so approved users can reach it from their devices; do not expose the database publicly.
2. Verify login, logout, account disablement, proxy headers, and secure-cookie behavior on staging.
3. Use a shared rate-limit store before scaling to multiple workers or instances.
