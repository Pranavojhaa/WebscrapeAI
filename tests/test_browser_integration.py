import os
import sys
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from smart_scrapper import SmartScraper


class DynamicPageHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        page = b"""<!doctype html>
<html><body><main id="content"></main>
<script>
window.setTimeout(() => {
  const article = document.createElement("article");
  article.className = "quote";
  article.textContent = "browser-rendered ".repeat(100);
  document.querySelector("#content").append(article);
}, 100);
</script>
</body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, format_string, *arguments):
        return


@unittest.skipUnless(
    os.getenv("RUN_SELENIUM_INTEGRATION") == "1",
    "Enable this test in the scheduled or manually dispatched browser workflow.",
)
class DynamicBrowserIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), DynamicPageHandler)
        cls.server_thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=5)

    def test_dynamic_renderer_waits_for_javascript_content(self):
        url = f"http://127.0.0.1:{self.server.server_port}/"
        with patch.dict(
            os.environ,
            {
                "ENABLE_SELENIUM": "true",
                "APP_ENV": "development",
                "RAILWAY_ENVIRONMENT": "",
            },
        ):
            soup = SmartScraper(url)._get_dynamic_soup()

        self.assertIsNotNone(soup)
        self.assertIsNotNone(soup.select_one("article.quote"))
        self.assertIn("browser-rendered", soup.get_text())
        self.assertGreater(len(soup.get_text()), 1000)


if __name__ == "__main__":
    unittest.main()
