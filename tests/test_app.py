import sys
import unittest
import os
from urllib.parse import urlsplit
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import app as web_app
from account_store import AccountStore
from network import URLSafetyError


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.environment_patch = patch.dict(os.environ, {"APP_ENV": "development", "APP_MODE": "private"}, clear=True)
        self.environment_patch.start()
        web_app.app.config.update(TESTING=True)
        web_app.account_stores.clear()
        for limiter in (
            web_app.auth_failure_limiter,
            web_app.login_request_limiter,
            web_app.password_reset_ip_limiter,
            web_app.password_reset_email_limiter,
            web_app.post_limiter,
            web_app.analysis_limiter,
        ):
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

    def test_unauthenticated_background_request_keeps_login_csrf_token(self):
        # Browsers fetch /favicon.ico after rendering /login; that redirect must not rotate the form token.
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
            client = web_app.app.test_client()
            csrf = self.read_csrf_token(client.get("/login").data)
            client.get("/favicon.ico", follow_redirects=True)
            login_response = client.post(
                "/login",
                data={"email": "owner@example.test", "password": "correct-horse-battery-staple", "csrf_token": csrf},
            )

        self.assertEqual(login_response.status_code, 302)

    def test_bootstrap_password_ignores_trailing_newline_from_secret(self):
        environment = {
            "APP_ENV": "production",
            "APP_MODE": "private",
            "DATABASE_URL": "sqlite:///:memory:",
            "BOOTSTRAP_ADMIN_EMAIL": "owner@example.test",
            "BOOTSTRAP_ADMIN_PASSWORD": "correct-horse-battery-staple\n",
            "APP_SECRET_KEY": "test-session-signing-key-that-is-long-enough-1234567890",
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(web_app, "has_production_credentials", return_value=True),
        ):
            client = web_app.app.test_client()
            csrf = self.read_csrf_token(client.get("/login").data)
            login_response = client.post(
                "/login",
                data={"email": "owner@example.test", "password": "correct-horse-battery-staple", "csrf_token": csrf},
            )

        self.assertEqual(login_response.status_code, 302)

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

    def test_login_page_disables_caching(self):
        response = self.client.get("/login")

        self.assertEqual(response.headers.get("Cache-Control"), "no-store")

    def test_login_rejects_a_csrf_token_without_a_session(self):
        fresh_client = web_app.app.test_client()
        response = fresh_client.post(
            "/login",
            data={"email": "owner@example.test", "password": "not-a-real-password", "csrf_token": "stale"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        self.assertIn(b"Invalid or expired form token", response.data)

    def test_login_accepts_session_mismatch_only_for_same_origin(self):
        class FailedAuthenticationStore:
            def authenticate(self, email, password):
                return None

        with patch.object(web_app, "ensure_account_store", return_value=FailedAuthenticationStore()):
            accepted = self.client.post(
                "/login",
                data={"email": "owner@example.test", "password": "not-a-real-password", "csrf_token": "other-session-token"},
                headers={"Origin": "http://localhost"},
            )
            rejected = self.client.post(
                "/login",
                data={"email": "owner@example.test", "password": "not-a-real-password", "csrf_token": "other-session-token"},
                headers={"Origin": "https://attacker.example"},
            )
            missing_origin = self.client.post(
                "/login",
                data={"email": "owner@example.test", "password": "not-a-real-password", "csrf_token": "other-session-token"},
            )
            missing_token = self.client.post(
                "/login",
                data={"email": "owner@example.test", "password": "not-a-real-password"},
                headers={"Origin": "http://localhost"},
            )
            malformed_origin = self.client.post(
                "/login",
                data={"email": "owner@example.test", "password": "not-a-real-password", "csrf_token": "other-session-token"},
                headers={"Origin": "http://[invalid"},
            )

        self.assertEqual(accepted.status_code, 200)
        self.assertIn(b"incorrect", accepted.data)
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(missing_origin.status_code, 400)
        self.assertEqual(missing_token.status_code, 400)
        self.assertEqual(malformed_origin.status_code, 400)

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

    def test_login_request_limit_applies_even_when_attempts_use_different_emails(self):
        store = AccountStore("sqlite:///:memory:")
        store.initialize("owner@example.test", "owner-test-password-long-enough")
        login_limiter = web_app.SlidingWindowLimiter(2, 15 * 60)
        post_limiter = web_app.SlidingWindowLimiter(100, 60)
        csrf = self.read_csrf_token(self.client.get("/login").data)
        with (
            patch.object(web_app, "ensure_account_store", return_value=store),
            patch.object(web_app, "login_request_limiter", login_limiter),
            patch.object(web_app, "post_limiter", post_limiter),
        ):
            responses = [
                self.client.post(
                    "/login",
                    data={"email": f"user{index}@example.test", "password": "wrong", "csrf_token": csrf},
                )
                for index in range(3)
            ]

        self.assertEqual([response.status_code for response in responses], [200, 200, 429])
        self.assertEqual(responses[-1].headers["Retry-After"], str(login_limiter.window))

    def test_password_reset_uses_neutral_email_and_completes_once(self):
        store = AccountStore("sqlite:///:memory:")
        store.initialize("owner@example.test", "owner-password-long-enough-for-test")
        settings = {
            "base_url": "https://private.example.test",
            "smtp_host": "smtp.example.test",
            "smtp_port": 587,
            "smtp_from": "WebScrapeAI <no-reply@example.test>",
            "smtp_username": "",
            "smtp_password": "",
        }
        sent_messages = []
        with (
            patch.dict(
                os.environ,
                {
                    "APP_ENV": "production",
                    "APP_MODE": "private",
                    "DATABASE_URL": "sqlite:///:memory:",
                    "BOOTSTRAP_ADMIN_EMAIL": "owner@example.test",
                    "BOOTSTRAP_ADMIN_PASSWORD": "owner-password-long-enough-for-test",
                    "APP_SECRET_KEY": "test-session-signing-key-that-is-long-enough-1234567890",
                },
                clear=True,
            ),
            patch.object(web_app, "has_production_credentials", return_value=True),
            patch.object(web_app, "ensure_account_store", return_value=store),
            patch.object(web_app, "password_reset_settings", return_value=settings),
            patch.object(
                web_app,
                "send_password_reset_email",
                side_effect=lambda email, reset_url, mail_settings: sent_messages.append((email, reset_url)),
            ),
        ):
            csrf = self.read_csrf_token(self.client.get("/password-reset").data)
            known = self.client.post(
                "/password-reset",
                data={"email": "owner@example.test", "csrf_token": csrf},
            )
            unknown = self.client.post(
                "/password-reset",
                data={"email": "nobody@example.test", "csrf_token": csrf},
            )

            self.assertEqual(known.status_code, 200)
            self.assertEqual(unknown.status_code, 200)
            self.assertIn(web_app.reset_request_message().encode(), known.data)
            self.assertIn(web_app.reset_request_message().encode(), unknown.data)
            self.assertEqual(len(sent_messages), 1)
            parsed_url = urlsplit(sent_messages[0][1])
            self.assertEqual(parsed_url.scheme, "https")
            self.assertEqual(parsed_url.path, "/password-reset")
            self.assertEqual(parsed_url.query, "")
            raw_token = parsed_url.fragment.removeprefix("token=")
            self.assertTrue(raw_token)

            old_session = web_app.app.test_client()
            old_csrf = self.read_csrf_token(old_session.get("/login").data)
            old_login = old_session.post(
                "/login",
                data={
                    "email": "owner@example.test",
                    "password": "owner-password-long-enough-for-test",
                    "csrf_token": old_csrf,
                },
            )
            self.assertEqual(old_login.status_code, 302)

            reset_response = self.client.post(
                "/password-reset/confirm",
                data={
                    "csrf_token": csrf,
                    "token": raw_token,
                    "password": "a-different-password-at-least-16-chars",
                },
            )
            self.assertEqual(reset_response.status_code, 302)
            self.assertIsNotNone(
                store.authenticate("owner@example.test", "a-different-password-at-least-16-chars")
            )
            self.assertIsNone(
                store.authenticate("owner@example.test", "owner-password-long-enough-for-test")
            )
            self.assertEqual(old_session.get("/").status_code, 302)

    def test_password_reset_email_throttle_keeps_neutral_response(self):
        store = AccountStore("sqlite:///:memory:")
        store.initialize("owner@example.test", "owner-password-long-enough-for-test")
        settings = {
            "base_url": "https://private.example.test",
            "smtp_host": "smtp.example.test",
            "smtp_port": 587,
            "smtp_from": "no-reply@example.test",
            "smtp_username": "",
            "smtp_password": "",
        }
        sent_to = []
        with (
            patch.object(web_app, "ensure_account_store", return_value=store),
            patch.object(web_app, "password_reset_settings", return_value=settings),
            patch.object(
                web_app,
                "send_password_reset_email",
                side_effect=lambda email, reset_url, mail_settings: sent_to.append(email),
            ),
        ):
            csrf = self.read_csrf_token(self.client.get("/password-reset").data)
            responses = [
                self.client.post(
                    "/password-reset",
                    data={"email": "owner@example.test", "csrf_token": csrf},
                )
                for _ in range(web_app.password_reset_email_limiter.limit + 1)
            ]

        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual(len(sent_to), web_app.password_reset_email_limiter.limit)
        self.assertTrue(
            all(web_app.reset_request_message().encode() in response.data for response in responses)
        )

    def test_password_reset_ip_limit_returns_retry_after(self):
        store = AccountStore("sqlite:///:memory:")
        store.initialize("owner@example.test", "owner-password-long-enough-for-test")
        settings = {
            "base_url": "https://private.example.test",
            "smtp_host": "smtp.example.test",
            "smtp_port": 587,
            "smtp_from": "no-reply@example.test",
            "smtp_username": "",
            "smtp_password": "",
        }
        ip_limiter = web_app.SlidingWindowLimiter(2, 900)
        with (
            patch.object(web_app, "ensure_account_store", return_value=store),
            patch.object(web_app, "password_reset_settings", return_value=settings),
            patch.object(web_app, "password_reset_ip_limiter", ip_limiter),
            patch.object(web_app, "post_limiter", web_app.SlidingWindowLimiter(100, 60)),
        ):
            csrf = self.read_csrf_token(self.client.get("/password-reset").data)
            responses = [
                self.client.post(
                    "/password-reset",
                    data={"email": f"unknown{index}@example.test", "csrf_token": csrf},
                )
                for index in range(3)
            ]

        self.assertEqual([response.status_code for response in responses], [200, 200, 429])
        self.assertEqual(responses[-1].headers["Retry-After"], str(ip_limiter.window))

    def test_password_reset_requires_mail_configuration(self):
        with patch.object(web_app, "password_reset_settings", side_effect=ValueError):
            csrf = self.read_csrf_token(self.client.get("/password-reset").data)
            response = self.client.post(
                "/password-reset",
                data={"email": "owner@example.test", "csrf_token": csrf},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn(b"Password recovery is not configured", response.data)

    def test_failed_email_delivery_removes_the_reset_token(self):
        store = AccountStore("sqlite:///:memory:")
        store.initialize("owner@example.test", "owner-password-long-enough-for-test")
        settings = {
            "base_url": "https://private.example.test",
            "smtp_host": "smtp.example.test",
            "smtp_port": 587,
            "smtp_from": "no-reply@example.test",
            "smtp_username": "",
            "smtp_password": "",
        }
        with (
            patch.object(web_app, "ensure_account_store", return_value=store),
            patch.object(web_app, "password_reset_settings", return_value=settings),
            patch.object(web_app, "send_password_reset_email", side_effect=RuntimeError("delivery failed")),
        ):
            csrf = self.read_csrf_token(self.client.get("/password-reset").data)
            response = self.client.post(
                "/password-reset",
                data={"email": "owner@example.test", "csrf_token": csrf},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(web_app.reset_request_message().encode(), response.data)
        with store._connection() as connection:
            count = connection.execute("SELECT COUNT(*) AS token_count FROM password_reset_tokens").fetchone()[
                "token_count"
            ]
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
