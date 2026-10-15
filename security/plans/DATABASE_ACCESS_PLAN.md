# DATABASE_ACCESS Fix Plan

## Changes

- Add a private PostgreSQL account store for production and SQLite support for local development/tests.
- Scope `DATABASE_URL` to the private Render environment and restrict database network access to internal connections.
- Keep the public demo dependency set and runtime free of database access.

## Verification goals

- [x] Account queries use bound parameters.
- [x] Demo has no database URL or account-store import.
- [ ] Verify external database connections are blocked on Render.
- [ ] Verify backup and restore behavior before relying on accounts.

## Manual verification

- Confirm only the private service can connect to Postgres.
- Review backup retention and test restoring the account database.
