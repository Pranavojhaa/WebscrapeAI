import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from src import demo_app
from src.demo_catalog import DEMO_SITES, SNAPSHOT_DATE


class PublicDemoTests(unittest.TestCase):
    def setUp(self):
        self.environment_patch = patch.dict(
            os.environ,
            {"APP_ENV": "production", "APP_MODE": "demo"},
            clear=True,
        )
        self.environment_patch.start()
        demo_app.app.config.update(TESTING=True)
        self.client = demo_app.app.test_client()

    def tearDown(self):
        self.environment_patch.stop()

    def test_catalog_contains_the_ten_curated_samples(self):
        self.assertEqual(len(DEMO_SITES), 10)
        self.assertEqual(sum(site["category"] == "Wikipedia · AI" for site in DEMO_SITES), 6)
        self.assertEqual(sum(site["category"].startswith("OpenAI") for site in DEMO_SITES), 3)
        self.assertEqual({site["snapshot_date"] for site in DEMO_SITES}, {SNAPSHOT_DATE})
        self.assertTrue(all(site["counts"]["headings"] >= len(site["headings"]) for site in DEMO_SITES))

    def test_home_shows_preloaded_sites_and_cached_mode(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No live requests", response.data)
        self.assertIn(b"OpenAI API quickstart", response.data)
        self.assertIn("script-src 'self'".encode(), response.headers["Content-Security-Policy"].encode())

    def test_submit_renders_a_fixture_without_network_access(self):
        with (
            patch("socket.getaddrinfo", side_effect=AssertionError("demo must stay offline")) as resolve,
            patch("socket.create_connection", side_effect=AssertionError("demo must stay offline")) as connect,
        ):
            response = self.client.post("/", data={"site_id": "wiki-ml", "prompt": "ignored user text"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Machine learning", response.data)
        self.assertIn(b"CACHED SCRAPE RESULT", response.data)
        self.assertIn(b"2922", response.data)
        self.assertIn(b"curated preview", response.data)
        resolve.assert_not_called()
        connect.assert_not_called()

    def test_arbitrary_sites_and_private_routes_are_not_available(self):
        invalid_site = self.client.post("/", data={"site_id": "https://127.0.0.1"})
        private_route = self.client.get("/admin/users")
        login_route = self.client.get("/login")

        self.assertIn(b"Choose one of the preloaded", invalid_site.data)
        self.assertEqual(private_route.status_code, 404)
        self.assertEqual(login_route.status_code, 404)

    def test_public_demo_refuses_private_configuration(self):
        with patch.dict(os.environ, {"APP_SECRET_KEY": "not-a-real-secret"}, clear=False):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 503)
        self.assertIn(b"cannot include private credentials", response.data)

    def test_public_demo_refuses_private_admin_configuration(self):
        with patch.dict(os.environ, {"BOOTSTRAP_ADMIN_EMAIL": "admin@example.test"}, clear=False):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 503)

    def test_service_fails_closed_when_mode_is_not_demo(self):
        with patch.dict(os.environ, {"APP_MODE": "private"}, clear=False):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
