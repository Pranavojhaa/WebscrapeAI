# PASSWORD_HASHING Fix Plan

## Changes

- Use Werkzeug salted password hashes for bootstrap and administrator-created accounts.
- Store only hashes in SQLite/PostgreSQL; never return them through routes or templates.
- Require at least 16 characters for administrator-provided passwords.

## Verification goals

- [x] Correct passwords authenticate; incorrect passwords fail.
- [x] Inactive accounts cannot authenticate.
- [x] Raw passwords are not returned by user queries or templates.
- [ ] Verify the pinned Werkzeug hash behavior during dependency review.

## Manual verification

- Remove the bootstrap password secret after first-admin initialization.
- Add password rotation/reset before broader invitations.
