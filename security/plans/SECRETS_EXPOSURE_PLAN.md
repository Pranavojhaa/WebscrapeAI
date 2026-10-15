# SECRETS_EXPOSURE Fix Plan

## Changes

None to existing files.

## New files

- `.env.example` — placeholder values only.

## Verification goals

- [x] `git ls-files .env` returns nothing
- [x] Secret-pattern grep across source and git history returns only the `test-key` placeholder
- [x] No public-prefixed env vars exist (no frontend build)
- [x] `.env.example` exists with placeholder values only
- [x] `/.env`, `/.git/config` and backup paths return 404 on the local server
- [ ] Same paths return 404 on the deployed app (not checked; no deployed URL was scanned)

## Manual verification (for the human)

- Run `gitleaks detect --source . --verbose`.
- Run the scanner against the Railway URL once deployed.
