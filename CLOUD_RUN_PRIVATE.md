# Private Cloud Run setup

This is a preparation runbook only. It does not create Google Cloud or Neon resources, enable billing, or deploy the service. Keep the existing Render demo unchanged.

## Target configuration

- Build the private app from this repository's `Dockerfile`; it runs `src.app:app` with one Gunicorn worker and four threads.
- Use Cloud Run in `asia-south1` (Mumbai), request-based billing, 1 vCPU, 1 GiB memory, zero minimum instances, one maximum instance, concurrency 4, and a 40-second request timeout. Zero minimum instances saves idle compute but introduces cold starts.
- Neon currently has no Mumbai region; use its Singapore region, `aws-ap-southeast-1`, as the closest listed APAC region.
- Use Neon’s pooled PostgreSQL connection string for `DATABASE_URL`, with TLS required. Keep this secret scoped to the private service.
- The Cloud Run URL must be reachable by invited users who may not have Google identities. Cloud Run IAM therefore cannot be the user login; the app’s own login must guard private features. The URL and login page are publicly reachable, but there is no public signup.

## Runtime settings

Set these non-secret environment values on the private service:

| Name | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `APP_MODE` | `private` |
| `BOOTSTRAP_ADMIN_EMAIL` | The previously chosen first-admin address; enter only in private deployment settings |
| `OPENAI_MODEL` | `gpt-5-mini` |
| `ENABLE_SELENIUM` | `false` |
| `TRUSTED_PROXY_HOPS` | `0` until Cloud Run's forwarded client-IP chain is verified |
| `PASSWORD_RESET_BASE_URL` | Canonical HTTPS origin of the private service, with no path |
| `SMTP_HOST` | Transactional email provider's SMTP host |
| `SMTP_PORT` | `587` (STARTTLS) or `465` (implicit TLS) |
| `SMTP_FROM` | Verified sender address for reset emails |

Store these values in Secret Manager, never in this repository, an image, or a local `.env` file:

| Secret-backed variable | Requirement |
| --- | --- |
| `APP_SECRET_KEY` | Unique random value, at least 32 characters |
| `DATABASE_URL` | Neon pooled connection URI with TLS enabled |
| `BOOTSTRAP_ADMIN_PASSWORD` | Unique password of at least 16 characters; remove its Cloud Run mapping after the first admin login |
| `OPENAI_API_KEY` | Optional; add only if private AI analysis is wanted |
| `SMTP_USERNAME` | Optional SMTP authentication username |
| `SMTP_PASSWORD` | Optional SMTP authentication password; configure only with `SMTP_USERNAME` |

Use a dedicated Cloud Run runtime service account and grant it Secret Manager access only to the required secrets. Do not give the demo service these secrets.
For secret-backed environment variables, pin numbered secret versions and deploy a new revision when rotating them; Cloud Run resolves environment-variable secrets when each instance starts.

## Database and first admin

On first private-app use, `AccountStore.initialize()` creates the `users` table and bootstraps the admin only if the table is empty. It also applies idempotent, transactional schema migrations: v1 records the existing-user-table baseline, v2 adds per-user session versions, and v3 creates the password-reset-token table. Back up the database before deploying schema changes and verify the migration on a staging database first.

After the first admin signs in, remove `BOOTSTRAP_ADMIN_PASSWORD` from the Cloud Run revision and Secret Manager access path; the database retains the account's password hash. Admins add approved users at `/admin/users`; there is no signup route. Use unique, temporary passwords and share them outside the app.

Password recovery is available at `/password-reset` after the canonical HTTPS base URL and SMTP settings are configured. Use a mail provider with TLS enabled and a verified sender domain. Reset links carry a random token in the URL fragment, so browsers do not send it in the HTTP request or access-log path; only its hash is stored in the database. Tokens expire after 30 minutes, work once, and increment the account's session version to invalidate existing sessions. The app returns the same confirmation for existing and unknown emails.

## Before inviting users

- Verify login, account creation/disablement, private routes, and database connectivity after a future deployment; `/health` only checks that the process responds and does not prove database readiness.
- Verify Cloud Run's forwarded client-IP chain before changing `TRUSTED_PROXY_HOPS`; the current rate limits key off client IP before login.
- Login is limited to 30 requests per source IP per 15 minutes and 10 failed attempts per source/email pair per 15 minutes. Password-reset requests are limited to 10 per source IP per 15 minutes and 3 per normalized email per hour. The general form-post limiter also applies. These rate limits are in-memory, reset on instance restart, and are not shared between instances; use a shared limiter before scaling or widening access.
- Configure and test SMTP delivery before enabling password recovery for users; no mail provider or Cloud Run secret is provisioned by this code change.
- The app rejects private/reserved scrape targets in code, but network-level outbound restrictions are not configured. Resolve the shared-rate-limit and outbound-egress controls before inviting other users.

No Cloud Run service, Neon project, database, secret, billing setting, or deployment was created during this preparation.
