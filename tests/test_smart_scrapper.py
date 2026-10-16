import os
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from types import SimpleNamespace

import smart_scrapper
import requests
from bs4 import BeautifulSoup
from network import URLSafetyError
from smart_scrapper import SmartScraper, dynamic_rendering_enabled, validate_soup


class DynamicRenderingConfigurationTests(unittest.TestCase):
    def test_dynamic_rendering_is_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(dynamic_rendering_enabled())

    def test_dynamic_rendering_requires_local_opt_in(self):
        environment = {"ENABLE_SELENIUM": "true", "APP_ENV": "development"}
        with patch.dict(os.environ, environment, clear=True):
            self.assertTrue(dynamic_rendering_enabled())

    def test_dynamic_rendering_is_blocked_in_production(self):
        for environment in (
            {"ENABLE_SELENIUM": "true", "APP_ENV": "Production"},
            {"ENABLE_SELENIUM": "true", "APP_ENV": "production"},
        ):
            with self.subTest(environment=environment), patch.dict(os.environ, environment, clear=True):
                self.assertFalse(dynamic_rendering_enabled())


class ContentSufficiencyTests(unittest.TestCase):
    def test_article_without_tables_is_accepted(self):
        paragraphs = "".join(f"<p>{'Paragraph text about HTTP. ' * 8}</p>" for _ in range(10))
        soup = BeautifulSoup(f"<html><body><h1>Overview</h1>{paragraphs}</body></html>", "html.parser")
        self.assertTrue(validate_soup(soup))

    def test_near_empty_and_script_only_pages_are_rejected(self):
        for html in (
            "<html><body><p>Loading…</p></body></html>",
            f"<html><body><div id='root'></div><script>{'var x = 1;' * 500}</script></body></html>",
        ):
            with self.subTest(html=html[:40]):
                self.assertFalse(validate_soup(BeautifulSoup(html, "html.parser")))


class FallbackTests(unittest.TestCase):
    ARTICLE = BeautifulSoup(f"<p>{'Rendered paragraph text. ' * 60}</p>", "html.parser")

    def test_failed_static_fetch_falls_back_to_browser(self):
        scraper = SmartScraper("https://example.test")
        with (
            patch.object(scraper, "_get_static_soup", side_effect=requests.HTTPError("403")),
            patch.object(scraper, "_get_dynamic_soup", return_value=self.ARTICLE) as dynamic,
        ):
            self.assertIs(scraper.get_soup(), self.ARTICLE)
        dynamic.assert_called_once()

    def test_failed_static_fetch_reraises_when_browser_is_off(self):
        scraper = SmartScraper("https://example.test")
        with (
            patch.object(scraper, "_get_static_soup", side_effect=requests.HTTPError("403")),
            patch.object(smart_scrapper, "dynamic_rendering_enabled", return_value=False),
            self.assertRaises(requests.HTTPError),
        ):
            scraper.get_soup()

    def test_blocked_url_never_reaches_browser(self):
        scraper = SmartScraper("http://10.0.0.1")
        with (
            patch.object(scraper, "_get_static_soup", side_effect=URLSafetyError("blocked")),
            patch.object(scraper, "_get_dynamic_soup") as dynamic,
            self.assertRaises(URLSafetyError),
        ):
            scraper.get_soup()
        dynamic.assert_not_called()


class DynamicRenderingTests(unittest.TestCase):
    def setUp(self):
        self.driver = MagicMock()
        self.driver.page_source = f"<html><body><table></table>{'content ' * 150}</body></html>"

        class FakeOptions:
            def add_argument(self, argument):
                pass

        class FakeWait:
            def __init__(self, driver, timeout):
                self.driver = driver

            def until(self, condition):
                return condition(self.driver)

        class FakeConditions:
            @staticmethod
            def presence_of_element_located(_locator):
                return lambda _driver: True

        self.fake_options = FakeOptions
        self.fake_wait = FakeWait
        self.fake_conditions = FakeConditions

    def _run_with_mocked_browser(self, max_response_bytes=None):
        patchers = [
            patch.object(smart_scrapper, "dynamic_rendering_enabled", return_value=True),
            patch.object(smart_scrapper, "SELENIUM_AVAILABLE", True),
            patch.object(smart_scrapper, "Options", self.fake_options),
            patch.object(smart_scrapper, "Service", None),
            patch.object(smart_scrapper, "WebDriverWait", self.fake_wait),
            patch.object(smart_scrapper, "EC", self.fake_conditions),
            patch.object(smart_scrapper, "webdriver", SimpleNamespace(Chrome=lambda **_kwargs: self.driver)),
            patch.object(smart_scrapper, "CHROMEDRIVER_PATH", None),
        ]
        if max_response_bytes is not None:
            patchers.append(patch.object(smart_scrapper, "MAX_RESPONSE_BYTES", max_response_bytes))

        with ExitStack() as stack:
            for patcher in patchers:
                stack.enter_context(patcher)
            return SmartScraper("https://example.test")._get_dynamic_soup()

    def test_dynamic_fetch_waits_for_content_and_closes_browser(self):
        result = self._run_with_mocked_browser()

        self.assertIsNotNone(result)
        self.assertIsNotNone(result.find("table"))
        self.driver.get.assert_called_once_with("https://example.test")
        self.driver.quit.assert_called_once()

    def test_oversized_rendered_page_is_discarded(self):
        result = self._run_with_mocked_browser(max_response_bytes=50)

        self.assertIsNone(result)
        self.driver.quit.assert_called_once()

    def test_browser_is_closed_after_navigation_error(self):
        self.driver.get.side_effect = RuntimeError("navigation failed")
        result = self._run_with_mocked_browser()

        self.assertIsNone(result)
        self.driver.quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
