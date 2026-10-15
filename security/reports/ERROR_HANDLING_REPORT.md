# ERROR_HANDLING Security Report

## Status: LOW (fixed; one item unverified on deploy)

## Findings

- `debug=False` is hardcoded in `src/app.py`; the Werkzeug debugger is not reachable. Live scan: no debug or API-docs endpoints, error pages are generic.
- Unexpected exceptions in the inspect flow are logged server-side and shown as a generic message.
- **LOW — library exception text shown to users.** `except (IndexError, ValueError) as exc: page_data["error"] = str(exc)` also caught `requests` exceptions that subclass `ValueError` (`InvalidURL`, `InvalidSchema`, `MissingSchema`) and displayed their text.
- **LOW — malformed `Content-Length`.** `int(content_length)` in `src/network.py` raised `ValueError` on a non-numeric header from the remote server, and that text was shown too.
- **WARN (scan) — `Server: Werkzeug/3.1.9 Python/3.14.7`.** This comes from the Flask development server. Production runs Gunicorn, which sends its own header; the selected host's response has not been checked.

## What's at risk

Minor information disclosure about libraries in use.

## What's already secure

Debug off, generic 500s, server-side logging with `app.logger.exception`, production auth errors are fixed strings.

## Recommendations

1. Catch `requests.RequestException` before the `ValueError` branch and show the generic message (done).
2. Ignore a non-numeric `Content-Length`; the streamed size cap still applies (done).
