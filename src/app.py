import os
import sys
import io
import json
import hmac
import hashlib
import ipaddress
import re
import secrets
import threading
import time
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv
from flask import Flask, g, redirect, render_template, request, send_file, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from account_store import AccountStore, AccountStoreError
from inspector import fetch_count, get_element_data
from network import URLSafetyError
from smart_scrapper import get_soup, validate_soup

load_dotenv()

ELEMENT_OPTIONS = {
    "paragraphs": "Paragraphs",
    "headings": "Headings",
    "images": "Images",
    "links": "Links",
    "quotes": "Quotes",
    "table": "Tables",
}


def is_production() -> bool:
    # Fail closed: anything not explicitly marked as development requires authentication.
    return os.getenv("APP_ENV", "").strip().lower() != "development"


def trusted_proxy_hops() -> int:
    value = os.getenv("TRUSTED_PROXY_HOPS", "0").strip()
    try:
        hops = int(value)
    except ValueError as error:
        raise RuntimeError("TRUSTED_PROXY_HOPS must be a non-negative integer.") from error
    if hops < 0:
        raise RuntimeError("TRUSTED_PROXY_HOPS must be a non-negative integer.")
    return hops


def secrets_match(supplied: str, expected: str) -> bool:
    # Bytes, because hmac.compare_digest raises TypeError on non-ASCII str input.
    return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))


class SlidingWindowLimiter:
    # Limits are in-memory and per worker process, and reset on restart. Move to Flask-Limiter
    # with a shared Redis store if that stops being good enough.
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self.hits: dict[str, list[float]] = {}
        self.lock = threading.Lock()

    def _recent(self, key: str, now: float) -> list[float]:
        recent = [hit for hit in self.hits.get(key, ()) if now - hit < self.window]
        if recent:
            self.hits[key] = recent
        else:
            self.hits.pop(key, None)
        return recent

    def blocked(self, key: str) -> bool:
        with self.lock:
            return len(self._recent(key, time.monotonic())) >= self.limit

    def record(self, key: str) -> None:
        with self.lock:
            now = time.monotonic()
            if len(self.hits) > 10_000:
                for stale in list(self.hits):
                    self._recent(stale, now)
            self.hits[key] = self._recent(key, now) + [now]

    def hit(self, key: str) -> bool:
        with self.lock:
            now = time.monotonic()
            recent = self._recent(key, now)
            if len(recent) >= self.limit:
                return False
            self.hits[key] = recent + [now]
            return True


auth_failure_limiter = SlidingWindowLimiter(10, 15 * 60)
post_limiter = SlidingWindowLimiter(30, 60)
analysis_limiter = SlidingWindowLimiter(20, 60 * 60)
account_stores: dict[str, AccountStore] = {}
account_stores_lock = threading.Lock()


def client_key() -> str:
    current_user = getattr(g, "current_user", None)
    if current_user and current_user.get("email") != "local development":
        digest = hashlib.sha256(current_user["email"].encode("utf-8")).hexdigest()
        return f"account:{digest}"
    # IPv6 clients usually control a whole /64, so limit per /64 rather than per address.
    try:
        address = ipaddress.ip_address(request.remote_addr or "")
    except ValueError:
        return "unknown"
    if address.version == 6:
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def login_attempt_key(email: str) -> str:
    normalized_email = email.strip().lower()
    digest = hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()
    return f"{client_key()}:login:{digest}"


def too_many_requests(limiter: SlidingWindowLimiter):
    return "Too many requests. Wait a few minutes and try again.", 429, {"Retry-After": str(limiter.window)}


def neutralize_formula(value: Any) -> Any:
    # Spreadsheet apps run cells starting with these characters as formulas (CSV/XLSX injection).
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        try:
            float(value)
        except ValueError:
            return "'" + value
    return value


def deployment_mode() -> str:
    return os.getenv("APP_MODE", "private").strip().lower()


def has_production_credentials() -> bool:
    secret_key = os.getenv("APP_SECRET_KEY", "")
    database_url = os.getenv("DATABASE_URL", "").strip()
    return len(secret_key) >= 32 and database_url.startswith(("postgres://", "postgresql://"))


def get_account_store() -> AccountStore:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise AccountStoreError("DATABASE_URL is required for the private app.")
    with account_stores_lock:
        if database_url not in account_stores:
            account_stores[database_url] = AccountStore(database_url)
        return account_stores[database_url]


def ensure_account_store() -> AccountStore:
    store = get_account_store()
    store.initialize(
        os.getenv("BOOTSTRAP_ADMIN_EMAIL", ""),
        os.getenv("BOOTSTRAP_ADMIN_PASSWORD", ""),
    )
    return store


def csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def valid_email(email: str) -> bool:
    return len(email) <= 254 and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) is not None


app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.update(
    SECRET_KEY=os.getenv("APP_SECRET_KEY") or secrets.token_hex(32),
    MAX_CONTENT_LENGTH=32 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=is_production(),
)
proxy_hops = trusted_proxy_hops()
if proxy_hops:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxy_hops)


@app.before_request
def enforce_production_authentication():
    mode = deployment_mode()
    if mode != "private":
        return {"error": "The private service must use APP_MODE=private."}, 503

    g.current_user = None
    if is_production():
        if request.path == "/health" or request.path.startswith("/static/"):
            return None
        if not has_production_credentials():
            return {"error": "Private app authentication or database is not configured."}, 503
        try:
            store = ensure_account_store()
        except AccountStoreError as error:
            return {"error": str(error)}, 503
        except Exception:
            app.logger.exception("Private account store initialization failed")
            return {"error": "Private account storage is unavailable."}, 503
        if request.path != "/login":
            email = session.get("user_email", "")
            user = store.get_user(email) if email else None
            if user is None or not user["is_active"]:
                session.clear()
                return redirect(url_for("login"))
            g.current_user = {"email": user["email"], "is_admin": user["is_admin"]}
    else:
        g.current_user = {"email": "local development", "is_admin": True}

    if request.method == "POST":
        supplied_token = request.form.get("csrf_token", "")
        expected_token = session.get("csrf_token", "")
        if not expected_token or not secrets_match(supplied_token, expected_token):
            return "Invalid or expired form token. Reload the page and try again.", 400
        if not post_limiter.hit(client_key()):
            return too_many_requests(post_limiter)
        if request.path == "/login":
            attempt_key = login_attempt_key(request.form.get("email", ""))
            if auth_failure_limiter.blocked(attempt_key):
                return too_many_requests(auth_failure_limiter)
        if request.form.get("action") == "analyze" and not analysis_limiter.hit(client_key()):
            return too_many_requests(analysis_limiter)
    return None


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
    )
    response.headers.setdefault("X-Frame-Options", "DENY")
    if is_production():
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def normalize_url(url: str) -> str:
    cleaned = url.strip()
    if cleaned and not cleaned.startswith(("http://", "https://")):
        return f"https://{cleaned}"
    return cleaned


def build_result_context(result: Any, selected_element: str, selected_label: str) -> dict[str, Any]:
    context: dict[str, Any] = {
        "label": selected_label,
        "count": 0,
        "kind": "empty",
        "headers": [],
        "rows": [],
        "items": [],
    }

    if result is None:
        return context

    if isinstance(result, pd.DataFrame):
        headers = [str(column) for column in result.columns.tolist()]
        rows = result.fillna("").values.tolist()
        context.update(
            {
                "count": len(rows),
                "kind": "table",
                "headers": headers,
                "rows": rows,
            }
        )
        return context

    if selected_element == "links":
        items = [
            {"text": item.get("text", ""), "href": item.get("href", "")}
            for item in result
        ]
        context.update(
            {
                "count": len(items),
                "kind": "links",
                "items": items,
            }
        )
        return context

    items = [{"content": str(item)} for item in result]
    context.update(
        {
            "count": len(items),
            "kind": "list",
            "items": items,
        }
    )
    return context


def build_export_response(result: Any, selected_element: str, export_format: str):
    if result is None:
        raise ValueError("There are no results to export.")

    buffer = io.BytesIO()
    if isinstance(result, pd.DataFrame):
        if export_format in ("csv", "xlsx"):
            result = result.map(neutralize_formula)
        if export_format == "csv":
            text_buffer = io.StringIO()
            result.to_csv(text_buffer, index=False)
            payload = text_buffer.getvalue().encode("utf-8")
            mimetype = "text/csv"
            extension = "csv"
        elif export_format == "json":
            payload = result.to_json(orient="records", force_ascii=False, indent=2).encode("utf-8")
            mimetype = "application/json"
            extension = "json"
        elif export_format == "xlsx":
            result.to_excel(buffer, index=False)
            payload = buffer.getvalue()
            mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            extension = "xlsx"
        else:
            raise ValueError("Choose CSV, JSON, or Excel for table exports.")
    else:
        if export_format == "json":
            payload = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
            mimetype = "application/json"
            extension = "json"
        elif export_format == "txt":
            if selected_element == "links":
                text = "\n".join(f"{item.get('text', '')}\t{item.get('href', '')}" for item in result)
            else:
                text = "\n\n".join(str(item) for item in result)
            payload = text.encode("utf-8")
            mimetype = "text/plain; charset=utf-8"
            extension = "txt"
        else:
            raise ValueError("Choose JSON or text for this export.")

    return send_file(
        io.BytesIO(payload),
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"webscrapeai-{selected_element}.{extension}",
    )


@app.route("/", methods=["GET", "POST"])
def index():
    token = csrf_token()

    page_data: dict[str, Any] = {
        "url": "",
        "selected_element": "paragraphs",
        "selected_label": ELEMENT_OPTIONS["paragraphs"],
        "table_index": 1,
        "summary": None,
        "result": None,
        "error": None,
        "validated": False,
        "analysis": None,
        "ai_enabled": bool(os.getenv("OPENAI_API_KEY")),
        "csrf_token": token,
        "current_user": getattr(g, "current_user", None),
    }

    if request.method == "POST":
        raw_url = request.form.get("url", "")
        selected_element = request.form.get("element", "paragraphs")
        action = request.form.get("action", "inspect")
        selected_label = ELEMENT_OPTIONS.get(selected_element, "Paragraphs")
        table_index = request.form.get("table_index", "1")

        page_data.update(
            {
                "url": raw_url,
                "selected_element": selected_element,
                "selected_label": selected_label,
                "table_index": table_index,
            }
        )

        if selected_element not in ELEMENT_OPTIONS:
            page_data["error"] = "Choose a supported content type."
            return render_template("index.html", element_options=ELEMENT_OPTIONS, **page_data)

        try:
            table_number = max(int(table_index), 1)
        except ValueError:
            table_number = 1
            page_data["table_index"] = "1"

        normalized_url = normalize_url(raw_url)
        if not normalized_url:
            page_data["error"] = "Enter a URL to inspect."
            return render_template("index.html", element_options=ELEMENT_OPTIONS, **page_data)

        try:
            soup = get_soup(normalized_url)
            if not validate_soup(soup, normalized_url):
                page_data["error"] = "This page does not look rich enough for meaningful scraping."
                return render_template("index.html", element_options=ELEMENT_OPTIONS, **page_data)

            page_data["validated"] = True
            page_data["url"] = normalized_url
            page_data["summary"] = fetch_count(soup)
            result = get_element_data(soup, selected_element, table_index=table_number - 1)
            page_data["result"] = build_result_context(result, selected_element, selected_label)
            if action == "export":
                return build_export_response(result, selected_element, request.form.get("export_format", "json"))
            if action == "analyze":
                if result is None:
                    page_data["error"] = "There are no results to analyse."
                else:
                    analysis_data = result.to_string(index=False) if isinstance(result, pd.DataFrame) else json.dumps(result, ensure_ascii=False)
                    from analyzer import analyze_scraped_data

                    page_data["analysis"] = analyze_scraped_data(
                        f"Page: {normalized_url}\nContent type: {selected_label}\n\n{analysis_data}"
                    )
        except URLSafetyError as exc:
            page_data["error"] = str(exc)
        except requests.RequestException:
            # Some requests errors subclass ValueError; keep their text out of the page.
            page_data["error"] = "Could not inspect the page. Check the URL and try again."
        except (IndexError, ValueError) as exc:
            page_data["error"] = str(exc)
        except Exception:
            app.logger.exception("Page inspection failed")
            page_data["error"] = "Could not inspect the page. Check the URL and try again."

    return render_template("index.html", element_options=ELEMENT_OPTIONS, **page_data)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        try:
            store = ensure_account_store()
            user = store.authenticate(email, password)
        except AccountStoreError as exception:
            return {"error": str(exception)}, 503
        except Exception:
            app.logger.exception("Private account lookup failed")
            return {"error": "Private account storage is unavailable."}, 503
        if user is None:
            auth_failure_limiter.record(login_attempt_key(email))
            error = "The email or password is incorrect, or this account is disabled."
        else:
            auth_failure_limiter.hits.pop(login_attempt_key(email), None)
            session.clear()
            session["user_email"] = user["email"]
            csrf_token()
            return redirect(url_for("index"))
    return render_template("login.html", error=error, csrf_token=csrf_token())


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/admin/users", methods=["GET", "POST"])
def admin_users():
    current_user = getattr(g, "current_user", None)
    if not current_user or not current_user["is_admin"]:
        return "Not found.", 404

    store = ensure_account_store()
    message = None
    error = None
    if request.method == "POST":
        action = request.form.get("action", "")
        email = request.form.get("email", "").strip().lower()
        try:
            if action == "create":
                password = request.form.get("password", "")
                if not valid_email(email):
                    raise AccountStoreError("Enter a valid email address.")
                if len(password) < 16:
                    raise AccountStoreError("Use a temporary password of at least 16 characters.")
                store.create_user(email, password)
                message = f"Account created for {email}. Share its temporary password securely."
            elif action in ("disable", "enable"):
                store.set_active(email, action == "enable", current_user["email"])
                message = f"Account {email} {'enabled' if action == 'enable' else 'disabled'}."
            else:
                error = "Choose a valid account action."
        except AccountStoreError as exception:
            error = str(exception)
        except Exception:
            app.logger.exception("Account management action failed")
            error = "The account change could not be saved. Try again."

    return render_template(
        "admin_users.html",
        current_user=current_user,
        users=store.list_users(),
        message=message,
        error=error,
        csrf_token=csrf_token(),
    )


@app.get("/health")
def health():
    return {"status": "ok", "mode": deployment_mode()}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=False)
