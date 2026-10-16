import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import app as web_app
from network import URLSafetyError, fetch_public_html


PUBLIC = [(2, 1, 6, "", ("93.184.216.34", 80))]
PRIVATE = [(2, 1, 6, "", ("127.0.0.1", 80))]


class SecurityRegressionTests(unittest.TestCase):
    def setUp(self):
        self.environment_patch = patch.dict(os.environ, {"APP_ENV": "development"}, clear=True)
        self.environment_patch.start()
        web_app.app.config.update(TESTING=True)
        web_app.account_stores.clear()
        for limiter in (
            web_app.auth_failure_limiter,
            web_app.login_request_limiter,
            web_app.password_reset_ip_limiter,
            web_app.password_reset_email_limiter,
            web_app.post_limiter,
            web_app.ai_limiter,
        ):
            limiter.hits.clear()
        self.client = web_app.app.test_client()
        page = self.client.get("/").data
        marker = b'name="csrf_token" value="'
        start = page.index(marker) + len(marker)
        self.csrf_token = page[start:page.index(b'"', start)].decode()

    def tearDown(self):
        self.environment_patch.stop()

    def test_dns_rebinding_is_blocked_at_connect_time(self):
        # First lookup (validation) is public, second (the real connection) is private.
        with (
            patch("network.socket.getaddrinfo", side_effect=[PUBLIC, PRIVATE]) as getaddrinfo,
            patch("urllib3.util.connection.create_connection") as create_connection,
            self.assertRaises(URLSafetyError),
        ):
            fetch_public_html("http://rebind.example/")

        self.assertEqual(getaddrinfo.call_count, 2)
        create_connection.assert_not_called()

    def test_connection_is_made_to_the_validated_address(self):
        with (
            patch("network.socket.getaddrinfo", return_value=PUBLIC),
            patch("urllib3.connection.connection.create_connection", side_effect=OSError("stop")) as create_connection,
            self.assertRaises(Exception),
        ):
            fetch_public_html("http://pinned.example/")

        self.assertEqual(create_connection.call_args.args[0], ("93.184.216.34", 80))

    def test_unset_app_env_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(self.client.get("/").status_code, 503)

    def test_non_ascii_csrf_token_is_rejected_not_crashed(self):
        response = self.client.post("/", data={"url": "example.test", "csrf_token": "é"})
        self.assertEqual(response.status_code, 400)

    def test_non_ascii_login_input_is_rejected_not_crashed(self):
        environment = {
            "APP_ENV": "production",
            "APP_MODE": "private",
            "DATABASE_URL": "sqlite:///:memory:",
            "BOOTSTRAP_ADMIN_EMAIL": "owner@example.test",
            "BOOTSTRAP_ADMIN_PASSWORD": "owner-test-password-long-enough",
            "APP_SECRET_KEY": "s" * 32,
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(web_app, "has_production_credentials", return_value=True),
        ):
            response = self.client.post(
                "/login",
                data={"email": "é@example.test", "password": "é", "csrf_token": self.csrf_token},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"email or password is incorrect", response.data)

    def test_security_headers(self):
        response = self.client.get("/")
        self.assertIn("object-src 'none'", response.headers["Content-Security-Policy"])
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertNotIn("Strict-Transport-Security", response.headers)
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=True):
            self.assertIn("max-age=31536000", self.client.get("/health").headers["Strict-Transport-Security"])

    def test_formula_cells_are_neutralized_in_spreadsheet_exports(self):
        self.assertEqual(web_app.neutralize_formula("=HYPERLINK(1)"), "'=HYPERLINK(1)")
        self.assertEqual(web_app.neutralize_formula("@SUM(A1)"), "'@SUM(A1)")
        self.assertEqual(web_app.neutralize_formula("-5.2"), "-5.2")
        self.assertEqual(web_app.neutralize_formula("plain"), "plain")

        frame = pd.DataFrame([["=1+1", "ok"]])
        with web_app.app.test_request_context():
            csv = web_app.build_export_response(frame, "table", "csv")
            csv.direct_passthrough = False
            self.assertIn(b"'=1+1", csv.get_data())
            json_export = web_app.build_export_response(frame, "table", "json")
            json_export.direct_passthrough = False
            self.assertNotIn(b"'=1+1", json_export.get_data())

    def test_only_http_links_are_rendered_as_anchors(self):
        links = [{"text": "bad", "href": "javascript:alert(1)"}, {"text": "good", "href": "https://example.com/a"}]
        with (
            patch.object(web_app, "get_soup", return_value=object()),
            patch.object(web_app, "validate_soup", return_value=True),
            patch.object(web_app, "fetch_count", return_value={"links": 2}),
            patch.object(web_app, "get_element_data", return_value=links),
        ):
            response = self.client.post(
                "/",
                data={"url": "example.test", "element": "links", "action": "inspect", "csrf_token": self.csrf_token},
            )

        self.assertIn(b'href="https://example.com/a"', response.data)
        self.assertNotIn(b'href="javascript:', response.data)


    def test_form_posts_are_rate_limited_per_client(self):
        data = {"url": "", "csrf_token": self.csrf_token}
        statuses = [self.client.post("/", data=data).status_code for _ in range(web_app.post_limiter.limit + 1)]
        self.assertEqual(statuses[:-1], [200] * web_app.post_limiter.limit)
        self.assertEqual(statuses[-1], 429)

        # A different client is unaffected.
        other = self.client.post("/", data=data, environ_base={"REMOTE_ADDR": "203.0.113.9"})
        self.assertEqual(other.status_code, 200)

    def test_spoofed_forwarded_for_does_not_change_the_key_without_trusted_proxy(self):
        data = {"url": "", "csrf_token": self.csrf_token}
        for index in range(web_app.post_limiter.limit):
            self.client.post("/", data=data, headers={"X-Forwarded-For": f"198.51.100.{index}"})
        response = self.client.post("/", data=data, headers={"X-Forwarded-For": "198.51.100.250"})
        self.assertEqual(response.status_code, 429)

    def test_ai_endpoints_have_their_own_limit(self):
        headers = {"X-CSRF-Token": self.csrf_token}
        with (
            patch.object(web_app, "ai_limiter", web_app.SlidingWindowLimiter(2, 60 * 60)),
            patch.object(web_app, "post_limiter", web_app.SlidingWindowLimiter(100, 60)),
        ):
            statuses = [self.client.post("/api/ask", json={"question": ""}, headers=headers).status_code for _ in range(3)]
            page_status = self.client.post("/api/page", json={"url": ""}, headers=headers).status_code
        self.assertEqual(statuses, [400, 400, 429])
        self.assertEqual(page_status, 429)

    def test_failed_logins_are_throttled_per_client_and_email(self):
        environment = {
            "APP_ENV": "production",
            "APP_MODE": "private",
            "DATABASE_URL": "sqlite:///:memory:",
            "BOOTSTRAP_ADMIN_EMAIL": "owner@example.test",
            "BOOTSTRAP_ADMIN_PASSWORD": "owner-test-password-long-enough",
            "APP_SECRET_KEY": "s" * 32,
        }
        login_data = {
            "email": "owner@example.test",
            "password": "wrong-password",
            "csrf_token": self.csrf_token,
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(web_app, "has_production_credentials", return_value=True),
        ):
            responses = [
                self.client.post("/login", data=login_data)
                for _ in range(web_app.auth_failure_limiter.limit)
            ]
            locked = self.client.post("/login", data=login_data)
            other_client = self.client.post(
                "/login",
                data=login_data,
                environ_base={"REMOTE_ADDR": "203.0.113.9"},
            )

        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual(locked.status_code, 429)
        self.assertIn("Retry-After", locked.headers)
        self.assertEqual(other_client.status_code, 200)

    def test_ipv6_clients_share_a_limit_per_64(self):
        with web_app.app.test_request_context(environ_base={"REMOTE_ADDR": "2001:db8:1:2:aaaa::1"}):
            first = web_app.client_key()
        with web_app.app.test_request_context(environ_base={"REMOTE_ADDR": "2001:db8:1:2:bbbb::9"}):
            second = web_app.client_key()
        self.assertEqual(first, second)

    def test_selenium_requires_explicit_development(self):
        from smart_scrapper import dynamic_rendering_enabled

        for environment in ({"ENABLE_SELENIUM": "true"}, {"ENABLE_SELENIUM": "true", "APP_ENV": "staging"}):
            with self.subTest(environment=environment), patch.dict(os.environ, environment, clear=True):
                self.assertFalse(dynamic_rendering_enabled())


if __name__ == "__main__":
    unittest.main()
