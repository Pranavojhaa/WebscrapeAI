# WebScrapeAI

A small Flask app and interactive CLI for inspecting public HTML pages. It extracts headings, paragraphs, images, links, quotes, and tables; the web app can export extracted data and optionally request a short AI analysis.

## Requirements

- Python 3.11 or newer
- A public HTTP/HTTPS page to inspect
- An OpenAI API key only if you want AI analysis
- A local Chrome/Chromium installation only if you explicitly enable Selenium rendering

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
APP_ENV=development python src/app.py
```

Open `http://127.0.0.1:5000`. The CLI is available with:

```bash
python src/main.py
```

AI analysis is opt-in and sends the selected extraction to OpenAI only when the user clicks **Analyse with AI**. Configure it in the server environment (or an untracked `.env` file locally):

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5-mini
```

Never commit `.env` or place a key in source code. The analysis input is truncated to 12,000 characters.

## Dynamic rendering

Static HTTP inspection is the default. Install `requirements-selenium.txt` and set both `ENABLE_SELENIUM=true` and `APP_ENV=development` for local use (rendering is off for any other `APP_ENV`, including an unset one); it then uses `CHROME_BIN` and `CHROMEDRIVER_PATH` if set, otherwise Selenium Manager. The renderer waits up to 10 seconds for meaningful page content, then falls back to the static response if it remains sparse. A local JavaScript-fixture browser smoke test is included; verify a compatible browser/driver on any host before enabling rendering there.

Do not enable browser rendering on an internet-facing service without a separate browser sandbox and outbound network restrictions. A webpage can cause the browser to request other network resources, so the URL checks used by static fetching are not a substitute for browser isolation.

## Deployment

Railway uses `railway.json`, installs the locked runtime dependencies from `requirements.txt`, and starts Gunicorn.

`requirements.txt` and `requirements-selenium.txt` are generated lock files: every package, including transitive ones, is pinned with hashes, so pip installs exactly what was audited. Edit the direct dependencies in `requirements.in` or `requirements-selenium.in`, then regenerate with the command in the lock file's header (`uv pip compile ... --universal --python-version 3.11 --generate-hashes`). `/health` is a liveness check, not a readiness check for AI or Selenium. Authentication is required unless `APP_ENV=development` is set explicitly, so a host with no `APP_ENV` fails closed (503 until credentials are configured); local development uses `APP_ENV=development` and binds only to `127.0.0.1`.

Before exposing the app publicly, complete these operational controls:

1. Set strong `APP_USERNAME`, `APP_PASSWORD`, and `APP_SECRET_KEY` values. Railway deployments fail closed (503 health) until all three are configured; the browser uses HTTP Basic authentication and form posts require a CSRF token.
2. The app limits each client to 10 failed logins per 15 minutes, 30 form posts per minute and 20 AI analyses per hour (429 with `Retry-After`; IPv6 clients are grouped per /64). The counters are in memory per Gunicorn worker, so with 2 workers the effective ceiling is up to double and resets on restart. On Railway the client address is taken from the last `X-Forwarded-For` entry; confirm after deploying that two clients get separate limits. A shared limiter or WAF in front is still worth adding for anything beyond light use.
3. Enforce outbound destination restrictions through a controlled egress proxy or network layer; application URL validation cannot fully prevent DNS rebinding. Railway Static Outbound IPs provide stable source addresses for allowlisting, not destination filtering.
4. Keep Selenium disabled in production; it is deliberately unavailable in Railway/production mode until it runs in an isolated worker with restricted egress.
5. Set `OPENAI_API_KEY` only if AI analysis is intended, and configure billing/usage limits with the provider.
6. Test the deployed service, health route, exports, AI configuration, and restart behavior in the target Railway project.

Use a password of at least 16 characters and an `APP_SECRET_KEY` of at least 32 characters. Generate the latter with `python -c 'import secrets; print(secrets.token_urlsafe(48))'`; store it as a Railway secret, not in the repository.

The app blocks non-public resolved IP addresses, follows only revalidated HTTP(S) redirects, limits fetched pages to 5 MB, and uses request timeouts. These are useful safeguards, not a replacement for network-level egress controls.

Do not expose the web app publicly until the egress controls above are in place. The safe interim release is the local CLI (`python src/main.py`).

## CI and release gates

GitHub Actions runs on pushes and pull requests. The required checks should be:

- `unit-tests (3.11)` and `unit-tests (3.12)`: install runtime and pinned CI tools, run Ruff's undefined/unused-name checks, the unit suite, and Python byte-compilation.
- `dependency-audit`: scan both the runtime and optional Selenium dependency sets for known vulnerabilities.

In the GitHub repository's branch protection or ruleset settings, require pull requests and all three checks above before merging to the default branch. This workflow does not deploy the app. The Selenium browser smoke test runs only on a scheduled or manually dispatched workflow; it uses a local JavaScript fixture, not an arbitrary external website.

A staging-to-production release is not configured yet. Before public release, configure GitHub `staging` and `production` environments, require a human reviewer for production, add a staging deploy and smoke-test job, then make the production deploy depend on staging success and the environment approval. Keep the current safe CLI-only fallback until restricted outbound egress is enforced for the hosted web app.

Run the local checks with:

```bash
python -m pip install -r .github/requirements-ci.txt
ruff check --select F src tests
python -m unittest discover -s tests -v
python -m compileall -q src tests
pip-audit -r requirements.txt -r requirements-selenium.txt
```
