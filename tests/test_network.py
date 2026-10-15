import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from network import URLSafetyError, fetch_public_html, validate_public_url


class PublicURLValidationTests(unittest.TestCase):
    def test_rejects_local_and_reserved_ip_addresses(self):
        for url in ("http://127.0.0.1", "http://169.254.169.254", "http://[::1]"):
            with self.subTest(url=url), self.assertRaises(URLSafetyError):
                validate_public_url(url)

    def test_rejects_non_http_schemes(self):
        with self.assertRaises(URLSafetyError):
            validate_public_url("file:///etc/passwd")

    def test_rejects_nonstandard_ports(self):
        with self.assertRaises(URLSafetyError):
            validate_public_url("https://8.8.8.8:22/")

    @patch("network.socket.getaddrinfo")
    def test_rejects_hostname_resolving_to_private_address(self, getaddrinfo):
        getaddrinfo.return_value = [(2, 1, 6, "", ("10.0.0.4", 443))]
        with self.assertRaises(URLSafetyError):
            validate_public_url("https://example.test")

    @patch("network.socket.getaddrinfo")
    def test_accepts_public_hostname(self, getaddrinfo):
        getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
        self.assertEqual(validate_public_url("https://example.test"), "https://example.test")

    @patch("network.requests.Session")
    def test_follows_and_revalidates_public_redirects(self, session_factory):
        session = session_factory.return_value
        redirect = MagicMock(status_code=302, headers={"Location": "https://8.8.8.8/page"})
        final = MagicMock(
            status_code=200,
            headers={"Content-Type": "text/html", "Content-Length": "4"},
        )
        final.iter_content.return_value = [b"<h1", b">x</h1>"]
        session.get.side_effect = [redirect, final]

        content, final_url = fetch_public_html("https://1.1.1.1/start")

        self.assertEqual(content, b"<h1>x</h1>")
        self.assertEqual(final_url, "https://8.8.8.8/page")
        self.assertEqual(session.get.call_count, 2)
        self.assertFalse(session.get.call_args_list[0].kwargs["allow_redirects"])
        self.assertFalse(session.trust_env)
        session.close.assert_called_once()

    @patch("network.requests.Session")
    def test_blocks_redirect_to_private_address(self, session_factory):
        session = session_factory.return_value
        redirect = MagicMock(status_code=302, headers={"Location": "http://127.0.0.1/admin"})
        session.get.return_value = redirect

        with self.assertRaises(URLSafetyError):
            fetch_public_html("https://8.8.8.8/start")

        self.assertEqual(session.get.call_count, 1)

    @patch("network.MAX_RESPONSE_BYTES", 3)
    @patch("network.requests.Session")
    def test_limits_response_size(self, session_factory):
        session = session_factory.return_value
        response = MagicMock(status_code=200, headers={"Content-Type": "text/html"})
        response.iter_content.return_value = [b"four"]
        session.get.return_value = response

        with self.assertRaises(URLSafetyError):
            fetch_public_html("https://8.8.8.8/")

    @patch("network.requests.Session")
    def test_rejects_non_html_before_reading_body(self, session_factory):
        session = session_factory.return_value
        response = MagicMock(status_code=200, headers={"Content-Type": "application/json"})
        session.get.return_value = response

        with self.assertRaises(URLSafetyError):
            fetch_public_html("https://8.8.8.8/")

        response.iter_content.assert_not_called()
        response.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
