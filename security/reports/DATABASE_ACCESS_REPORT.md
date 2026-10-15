# DATABASE_ACCESS Security Report

## Status: Implemented; hosted verification pending

## Findings

The private app stores approved-user accounts in PostgreSQL in production. SQLite is supported for local development and tests. The schema contains email, password hash, admin/active flags, and creation time; it does not store scrape contents or API keys.

`DATABASE_URL` is read from the private service environment. The Render Blueprint places the database in the private environment, enables environment network isolation, and configures an empty IP allowlist so connections are internal only. The demo has no database URL or account-store import.

## What's at risk

- Database access control has not been verified against a live Render environment.
- Anyone with access to the private service's environment or Render workspace can access the database credentials.
- The app has no account deletion or audit-log feature.

## What's already secure

- The application uses a separate database for private accounts, not the public demo.
- Passwords are stored only as hashes; OpenAI keys and scrape content are not stored in the database.
- Account queries bind user values as parameters.
- Database network access is configured as private in the deployment blueprint.

## Recommendations

1. Verify the database is unreachable from outside Render and accessible from the private service after provisioning.
2. Keep database credentials restricted to the private service and trusted Render operators.
3. Enable backups and confirm the restore process before relying on accounts.
