# PASSWORD_HASHING Security Report

## Status: Implemented; hosted verification pending

## Findings

`src/account_store.py` stores password hashes created and verified with Werkzeug's password-hashing helpers. Raw passwords are not stored. The bootstrap admin and admin-created member passwords must be at least 16 characters. Password verification succeeds only for active accounts.

## What's at risk

- Operators who can read the Render environment can read the bootstrap password until it is removed after first-admin initialization.
- Admins distribute a member's initial password out of band. Members cannot change or reset it in the current UI.
- Password hash settings inherit from the pinned Werkzeug dependency; the algorithm should be re-reviewed when that dependency is upgraded.

## What's already secure

- Per-password salted hashes are used rather than reversible encryption or plaintext.
- Passwords are never returned by account listing or templates.
- The production bootstrap and OpenAI values are set as private-service environment secrets, not source or GitHub variables.

## Recommendations

1. Remove `BOOTSTRAP_ADMIN_PASSWORD` after the first admin can sign in.
2. Add password rotation/reset before inviting more users.
3. Re-run password-hashing review whenever Werkzeug is upgraded.
