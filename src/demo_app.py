import os

from flask import Flask, render_template, request

from src.demo_catalog import DEMO_SITE_BY_ID, DEMO_SITES


app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 4096

PRIVATE_ENVIRONMENT_KEYS = (
    "APP_SECRET_KEY",
    "APP_USERNAME",
    "APP_PASSWORD",
    "DATABASE_URL",
    "BOOTSTRAP_ADMIN_EMAIL",
    "BOOTSTRAP_ADMIN_PASSWORD",
    "OPENAI_API_KEY",
)


@app.before_request
def enforce_demo_isolation():
    if os.getenv("APP_MODE", "").strip().lower() != "demo":
        return {"error": "The demo service must use APP_MODE=demo."}, 503
    if any(os.getenv(key, "").strip() for key in PRIVATE_ENVIRONMENT_KEYS):
        return {"error": "The public demo cannot include private credentials or databases."}, 503
    if request.path not in ("/", "/health") and not request.path.startswith("/static/"):
        return "Not found.", 404
    return None


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
    )
    response.headers.setdefault("X-Frame-Options", "DENY")
    if os.getenv("APP_ENV", "").strip().lower() == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.route("/", methods=["GET", "POST"])
def index():
    submitted = request.method == "POST"
    site_id = request.form.get("site_id", DEMO_SITES[0]["id"]) if submitted else DEMO_SITES[0]["id"]
    selected_site = DEMO_SITE_BY_ID.get(site_id)
    error = None
    result = selected_site if submitted else None
    if selected_site is None:
        selected_site = DEMO_SITES[0]
        result = None
        error = "Choose one of the preloaded sample websites."
    return render_template(
        "demo.html",
        sites=DEMO_SITES,
        selected_site=selected_site,
        result=result,
        error=error,
    )


@app.get("/health")
def health():
    return {"status": "ok", "mode": "demo"}, 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5001")), debug=False)
