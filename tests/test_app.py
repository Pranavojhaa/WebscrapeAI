import sys
import unittest
import os
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import app as web_app
from network import URLSafetyError


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.environment_patch = patch.dict(os.environ, {"APP_ENV": "development", "APP_MODE": "private"}, clear=True)
        self.environment_patch.start()
        web_app.app.config.update(TESTING=True)
        web_app.account_stores.clear()
        for limiter in (web_app.auth_failure_limiter, web_app.post_limiter, web_app.analysis_limiter):
            limiter.hits.clear()
        self.client = web_app.app.test_client()
        initial_response = self.client.get("/")
        self.csrf_token = self.read_csrf_token(initial_response.data)

    @staticmethod
    def read_csrf_token(response_data):
        marker = b'name="csrf_token" value="'
        token_start = response_data.index(marker) + len(marker)
        token_end = response_data.index(b'"', token_start)
        return response_data[token_start:token_end].decode()

    def tearDown(self):
        self.environment_patch.stop()

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok", "mode": "private"})

    def test_production_requires_credentials(self):
        with patch.dict(os.environ, {"APP_ENV": "production", "APP_MODE": "private"}, clear=True):
            home_response = self.client.get("/")
            health_response = self.client.get("/health")

        self.assertEqual(home_response.status_code, 503)
        self.assertEqual(health_response.status_code, 200)

    def test_production_rejects_weak_secrets(self):
        environment = {
            "APP_ENV": "production",
            "APP_MODE": "private",
            "DATABASE_URL": "postgresql://user:password@localhost/database",
            "APP_SECRET_KEY": "too-short",
        }
        with patch.dict(os.environ, environment, clear=True):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 503)

    def test_production_authentication_protects_routes(self):
        environment = {
            "APP_ENV": "production",
            "APP_MODE": "private",
            "DATABASE_URL": "sqlite:///:memory:",
            "BOOTSTRAP_ADMIN_EMAIL": "owner@example.test",
            "BOOTSTRAP_ADMIN_PASSWORD": "correct-horse-battery-staple",
            "APP_SECRET_KEY": "test-session-signing-key-that-is-long-enough-1234567890",
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(web_app, "has_production_credentials", return_value=True),
        ):
            unauthorized = web_app.app.test_client().get("/")
            login_page = self.client.get("/login")
            csrf = self.read_csrf_token(login_page.data)
            login_response = self.client.post(
                "/login",
                data={
                    "email": "owner@example.test",
                    "password": "correct-horse-battery-staple",
                    "csrf_token": csrf,
                },
            )
            authorized = self.client.get("/")

        self.assertEqual(unauthorized.status_code, 302)
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(authorized.status_code, 200)
        self.assertIn("Content-Security-Policy", authorized.headers)
        self.assertIn(b"Private scraping workspace", authorized.data)

    def test_production_health_check_is_public_when_configured(self):
        environment = {
            "APP_ENV": "production",
            "APP_MODE": "private",
            "APP_SECRET_KEY": "test-session-signing-key-that-is-long-enough-1234567890",
        }
        with patch.dict(os.environ, environment, clear=True):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)

    def test_private_service_rejects_demo_mode(self):
        with (
            patch.dict(os.environ, {"APP_ENV": "production", "APP_MODE": "demo"}, clear=True),
        ):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 503)

    def test_post_requires_csrf_token(self):
        with patch.object(web_app, "get_soup") as get_soup:
            response = self.client.post(
                "/",
                data={"url": "example.test", "element": "headings", "action": "inspect"},
            )

        self.assertEqual(response.status_code, 400)
        get_soup.assert_not_called()

    def test_home_page_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Private scraping workspace", response.data)

    def test_inspection_renders_results(self):
        with (
            patch.object(web_app, "get_soup", return_value=object()),
            patch.object(web_app, "validate_soup", return_value=True),
            patch.object(web_app, "fetch_count", return_value={"headings": 1}),
            patch.object(web_app, "get_element_data", return_value=["A title"]),
        ):
            response = self.client.post(
                "/",
                data={"url": "example.test", "element": "headings", "action": "inspect", "csrf_token": self.csrf_token},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"A title", response.data)
        self.assertIn(b"Download results", response.data)

    def test_rejects_unsupported_element_before_fetching(self):
        with patch.object(web_app, "get_soup") as get_soup:
            response = self.client.post(
                "/",
                data={"url": "example.test", "element": "shell", "action": "inspect", "csrf_token": self.csrf_token},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Choose a supported content type", response.data)
        get_soup.assert_not_called()

    def test_displays_safe_url_errors(self):
        with patch.object(web_app, "get_soup", side_effect=URLSafetyError("Private addresses are blocked.")):
            response = self.client.post(
                "/",
                data={"url": "http://127.0.0.1", "element": "paragraphs", "csrf_token": self.csrf_token},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Private addresses are blocked", response.data)

    def test_exports_table_as_csv(self):
        table = pd.DataFrame([["Ada", "Analytical Engine"]], columns=["Name", "Work"])
        with (
            patch.object(web_app, "get_soup", return_value=object()),
            patch.object(web_app, "validate_soup", return_value=True),
            patch.object(web_app, "fetch_count", return_value={"table": 1}),
            patch.object(web_app, "get_element_data", return_value=table),
        ):
            response = self.client.post(
                "/",
                data={
                    "url": "example.test",
                    "element": "table",
                    "action": "export",
                    "export_format": "csv",
                    "csrf_token": self.csrf_token,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response.headers["Content-Disposition"])
        self.assertEqual(response.data.decode(), "Name,Work\nAda,Analytical Engine\n")

    def test_ai_analysis_is_explicitly_user_triggered(self):
        with (
            patch.object(web_app, "get_soup", return_value=object()),
            patch.object(web_app, "validate_soup", return_value=True),
            patch.object(web_app, "fetch_count", return_value={"headings": 1}),
            patch.object(web_app, "get_element_data", return_value=["A title"]),
            patch("analyzer.analyze_scraped_data", return_value="A concise analysis."),
        ):
            response = self.client.post(
                "/",
                data={"url": "example.test", "element": "headings", "action": "analyze", "csrf_token": self.csrf_token},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"A concise analysis", response.data)


if __name__ == "__main__":
    unittest.main()
