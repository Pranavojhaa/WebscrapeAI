# WebScrapeAI

A Flask app and CLI for extracting headings, paragraphs, images, links, quotes, and tables from public HTML pages. The private app reads a page, then (when an OpenAI key is configured) gives an overview, key findings with quotes checked against the page text, and clickable follow-up questions; it can also export the extracted data. The separate public demo uses only bundled sample data.

## Two hosted apps

`render.yaml` defines two independent Render web services and a private Postgres database for private accounts. Each web service gets its own Render URL and service-scoped environment variables. Both services and the database are pinned to Singapore and Python 3.12.11; the database accepts only internal Render connections.

- **Public demo (`src.demo_app:app`, `APP_MODE=demo`)**: a curated sidebar of ten cached page snapshots: Harvard CS50 AI, six AI-related Wikipedia pages, and three OpenAI developer pages. Selecting a sample fills a chat-style prompt; submitting it renders captured page-element counts, headings, related links, and a static overview. These snapshots were fetched from the linked sources on 2026-10-15. This separate entry point has no arbitrary URL field, makes no outbound scrape requests, imports no scraper or AI code, has no user database, and fails closed if private credentials are configured. Its minimal dependency lock excludes the AI client. Results are curated previews, not complete copies, and do not update when source pages change.
- **Private workspace (`APP_MODE=private`)**: an invite-only login for the owner and approved users. The first admin is bootstrapped from `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD`; admins create and disable member accounts at `/admin/users`. Passwords are stored as Werkzeug password hashes. There is no public signup. The private service alone receives the Postgres URL and optional `OPENAI_API_KEY`.

The private service must remain a public Render web service protected by the app's login, not a Render Private Service: approved users need to reach the sign-in page from their devices over the internet. Its URL is publicly reachable, but scraping and AI routes require an active account. The public demo and private workspace use separate Render environments with network isolation; the Postgres allowlist is empty, so only the private environment can reach it. Network isolation blocks private Render network traffic between environments; it does not block public internet access. The private app can still reach public scrape targets, while the demo app has no runtime fetch code. Render requires a Pro workspace for this isolation feature.

The Blueprint selects always-on paid service plans and a paid Postgres plan so the demo avoids free-tier sleep and the private account database does not expire. As of 2026-10-15, budget about $45/month before database storage, usage, or tax: the $25 Pro workspace, two $7 Starter web services, and $6 Basic-256MB Postgres. Recheck Render's displayed total before provisioning; this Blueprint does not create resources by itself.

## Render setup

1. Connect the repository to Render and create a Blueprint using `render.yaml`.
2. Review the services and database, the plans and costs shown by Render, and the branch selected before provisioning. This file does not create or deploy resources by itself.
3. Set the prompted private-service values: the first admin's email, a unique password of at least 16 characters, and the OpenAI key if AI is wanted. Render generates a separate `APP_SECRET_KEY` for the private service; the demo receives no API, database, or application secret.
4. After confirming that the first admin can sign in, remove `BOOTSTRAP_ADMIN_PASSWORD` from the private service's environment; the initialized database retains the account and its password hash.
5. Keep Selenium disabled. Verify the forwarded client-IP behavior before changing `TRUSTED_PROXY_HOPS` from `0`.
6. After provisioning, test both URLs separately: the demo should list ten samples and return cached data without external requests; the private URL should redirect to sign-in, allow only active accounts, support account disablement, and run scraping/AI only in the private service.

## Main branch protection

Recommended `main` defaults: require pull requests, one approval, resolved review conversations, and all CI results: `unit-tests (3.11)`, `unit-tests (3.12)`, `dependency-audit`, and `browser-smoke`. Dismiss stale approvals after new commits, block force-pushes/deletion, and apply protections to administrators. Browser smoke runs on pull requests so it can be required rather than silently skipped. Recheck the exact status-check names in GitHub before saving the rule; this recommendation does not configure GitHub settings.

Render's outbound static IPs identify the private service to other systems; they are not destination-egress restrictions. Environment isolation does not restrict public outbound connections. Static scraping has application-level public-IP checks, revalidates redirects, and pins resolved addresses at connection time. Keep Selenium off in hosted environments because browser rendering has a broader network surface. Add network-level egress controls if the hosting architecture supports them before allowing untrusted or broader access.

The deployment blueprint omits `OPENAI_API_KEY` and `DATABASE_URL` from the demo and links `DATABASE_URL` only to the private service. Do not copy private environment variables between services. Keep all real values in Render's environment settings, never in `.env.example`, source, or GitHub.

## Local setup

- Python 3.11 or newer
- A public HTTP/HTTPS page to inspect in private mode
- An OpenAI API key only if you want AI overviews and questions
- A local Chrome/Chromium installation only if you explicitly enable Selenium for local development

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
APP_ENV=development APP_MODE=private python src/app.py
```

Open `http://127.0.0.1:5000`. Explicit development mode bypasses login and binds to localhost; do not use it on a public host. The CLI is available with:

```bash
python src/main.py
```

To run only the read-only demo locally, use `APP_ENV=production APP_MODE=demo python -m src.demo_app`. No database or secret is required for demo mode; it serves locally at `http://127.0.0.1:5001`.

## AI and scraping safeguards

AI answers are optional. When `OPENAI_API_KEY` is set, a signed-in private user who reads a page sends its title, headings and paragraph text (truncated to 12,000 characters) to OpenAI for an overview, and each question they ask sends the same text plus recent turns. Quotes are shown only when they appear word for word in the page text. Conversations are kept in server memory for two hours per session and are lost on restart; move them to the database before running more than one instance. Configure `OPENAI_API_KEY` and, optionally, `OPENAI_MODEL` in the private service only.

Static HTTP inspection is the default. Dynamic rendering is limited to explicit local development (`ENABLE_SELENIUM=true` and `APP_ENV=development`); it is disabled in both hosted modes. Static fetches allow only standard HTTP/HTTPS ports, block non-public IP addresses, revalidate each redirect, pin DNS resolution to the connection, cap responses at 5 MB, and use timeouts. These are application-layer safeguards, not a substitute for network controls if the service later handles untrusted users or broader workloads.

Password recovery uses random one-time tokens stored only as hashes, expires them after 30 minutes, and invalidates existing sessions after a successful reset. Reset email is enabled only when the canonical HTTPS base URL and SMTP settings are configured. Login attempts are limited to 30 requests per source IP per 15 minutes and 10 failures per source/email pair per 15 minutes; password-reset requests are limited to 10 per source IP per 15 minutes and 3 per normalized email per hour. The general form-post limit and an AI limit of 60 page reads and questions per account per hour also apply. All limits are in-memory, reset on restart, and are not shared between instances; use a shared limiter before scaling or widening access.

`/health` is a public liveness route. It does not verify AI configuration or database readiness. The private service returns a configuration error on other routes if its secret, PostgreSQL connection, or first-admin bootstrap is missing.

## CI and release gates

GitHub Actions runs on pushes and pull requests. Recommended required check results for `main` are:

- `unit-tests (3.11)`
- `unit-tests (3.12)`
- `dependency-audit`
- `browser-smoke`

Also require pull requests, one approval, and resolved review conversations before merging. If no independent reviewer is available, decide explicitly whether to allow zero approvals for solo PRs. The current workflow does not deploy the app; browser smoke tests a local fixture on pull requests, scheduled runs, and manual dispatch.

## Dependencies and checks

`requirements.txt`, `requirements-demo.txt`, and `requirements-selenium.txt` are generated hash-locked files. Edit direct dependencies in the corresponding `.in` file, then regenerate with:

```bash
uv pip compile requirements.in --universal --python-version 3.11 --generate-hashes -o requirements.txt
uv pip compile requirements-demo.in --universal --python-version 3.11 --generate-hashes -o requirements-demo.txt
```

Run checks locally with:

```bash
python -m pip install -r .github/requirements-ci.txt
ruff check --select F src tests
python -m unittest discover -s tests -v
python -m compileall -q src tests
pip-audit -r requirements.txt -r requirements-selenium.txt -r requirements-demo.txt
```
