# SSRF Security Report

## Status: MEDIUM (fixed; residual risk noted)

## Findings

Fetching a user-supplied URL is the app's core feature. Every path (`smart_scrapper._get_static_soup`, `soup.fetch_page`) goes through `network.fetch_public_html`.

Live probes against the local server, all correctly refused: `http://localhost/`, `http://169.254.169.254/`, `http://[::1]/`, `http://[::ffff:127.0.0.1]/`, `http://0x7f.1/`, `http://2130706433/`, `file:///etc/passwd`, `http://example.com:8080/`, `http://user:pw@example.com/`, and the app's own `http://127.0.0.1:5057/health`.

- **MEDIUM — DNS rebinding (check and use were separate lookups).** `validate_public_url` resolved the hostname and checked the addresses, then `requests` resolved it again to connect. A hostname whose DNS answer flips from a public to a private address between the two lookups reached internal services. The README acknowledged this.
- **LOW — no overall time limit.** The `(5, 15)` timeout applies per read, so a server sending one byte every few seconds could hold a worker thread for a very long time. With 2 workers and 2 threads, four such requests stall the app.
- **LOW — Selenium path.** `driver.get(self.url)` follows redirects and loads subresources with no address checks, and runs Chrome with `--no-sandbox`. It was reachable when `ENABLE_SELENIUM` was truthy and `APP_ENV` was anything but `production`, including unset, which no longer matched the app's fail-closed auth. Fixed 2026-10-15: rendering now requires `APP_ENV=development` explicitly, so it only runs where the person submitting URLs is the person running the app. In-browser address checks were not added: closing this properly for a hosted service needs a filtering proxy for every browser request, which is only worth building if Selenium is wanted in production. `--no-sandbox` is unchanged.

## What's at risk

Reading cloud metadata endpoints, internal admin panels or other services on the host's private network, and returning their content to the requester.

## What's already secure

Scheme allowlist, standard ports only, userinfo rejected, every resolved address must be `is_global`, redirects followed manually and revalidated per hop (max 5), 5 MB cap, HTML content types only, `trust_env=False` so proxy env vars are ignored.

## Recommendations

1. Validate the address at connect time and connect to exactly that address (done).
2. Cap total fetch time (done, 30 s).
3. Keep Selenium off anywhere reachable from the internet; still add network-level egress restrictions as defence in depth.
