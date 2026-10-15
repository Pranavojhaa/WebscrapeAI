# SECRETS_EXPOSURE Security Report

## Status: LOW (fixed)

## Findings

- `.env` is in `.gitignore`, is not tracked (`git ls-files .env` is empty) and has never been added in any of the 8 commits.
- A regex search of the working tree and of `git log --all -p` for `sk-`, `sk_live_`, `sk_test_`, `AKIA`, `Bearer`, and quoted `password/secret/token/api_key` assignments found only the placeholder `api_key="test-key"` in `tests/test_analyzer.py`.
- Private-service secrets are read from environment variables: `OPENAI_API_KEY`, `APP_SECRET_KEY`, `DATABASE_URL`, `BOOTSTRAP_ADMIN_EMAIL`, and `BOOTSTRAP_ADMIN_PASSWORD`. The shared `APP_USERNAME`/`APP_PASSWORD` credentials were removed in favor of per-account password hashes.
- `render.yaml` gives the demo and private app separate environments. Only the private environment receives the database URL, bootstrap credentials, and optional OpenAI key; the demo has no secret or DB dependency.
- Flask serves only `src/static/` (one file, `styles.css`). Live scan on the local server: `/.env`, `/.git/config`, backup and dump paths all 404; no directory listing.
- **Gap (LOW):** there was no `.env.example`, so the required variables were documented only in prose.
- `gitleaks` is not installed, so history was checked with the regex search above, not a dedicated scanner.

## What's at risk

Nothing is currently exposed. Without an example file, a contributor is more likely to invent an ad hoc config file that is not ignored.

## What's already secure

`.env` ignored and never committed; the previous hardcoded `CHROMEDRIVER_PATH` was already replaced with an env lookup; no secret reaches a template or public demo response.

## Recommendations

1. Add `.env.example` with placeholders only (done).
2. Remove `BOOTSTRAP_ADMIN_PASSWORD` after the first admin is initialized.
3. Install `gitleaks` (`brew install gitleaks`) and scan the full history before publishing the deployment branch.
