# ACCESS_CONTROL Security Report

## Status: Implemented; hosted verification pending

## Findings

Production private-mode requests require an active account in the private Postgres database. There is no public signup. The first administrator is bootstrapped from environment secrets; administrators can create, disable, and re-enable member accounts at `/admin/users`. Disabled accounts are rejected on the next request.

Admin routes check the role on the server and return 404 to non-admin users. The last active administrator cannot disable itself or another account while it is the only active administrator. All state-changing forms require a session CSRF token.

There are no per-user saved scrape records or ownership-scoped resources. Scrape results are request-scoped.

## What's at risk

- The private Render URL is internet-reachable so approved people can sign in from their devices; the Flask session login is the access control, not Render network authentication.
- Admin-created members receive a temporary password out of band. There is no self-service password-change or reset route yet.
- Live authorization and account-disable behavior remain unverified until staging is provisioned.

## What's already secure

- Each account has an independent salted password hash; no public signup exists.
- Session cookies are HTTP-only, SameSite=Lax, and Secure in production.
- The public demo uses a separate app entry point and no account database.
- The Render Blueprint places the private service and database in the private environment, separate from the demo environment.

## Recommendations

1. Verify member creation, disablement, and re-enablement on staging before inviting users.
2. Add password rotation/reset before wider use.
3. Keep access to the Render workspace limited to trusted operators; app users do not need workspace access.
