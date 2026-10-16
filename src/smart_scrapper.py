import os
import shutil

from bs4 import BeautifulSoup
from network import MAX_RESPONSE_BYTES, fetch_public_html

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
    SELENIUM_AVAILABLE = True
except ImportError:
    webdriver = None
    Options = None
    Service = None
    WebDriverWait = None
    EC = None
    TimeoutException = Exception
    SELENIUM_AVAILABLE = False

    class By:
        CLASS_NAME = "class name"
        TAG_NAME = "tag name"

CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH") or shutil.which("chromedriver")
def dynamic_rendering_enabled():
    return (
        os.getenv("ENABLE_SELENIUM", "false").strip().lower() in {"1", "true", "yes"}
        # Fail closed like app.is_production(): the browser has no per-request address checks,
        # so it only runs where the person submitting URLs is the person running it.
        and os.getenv("APP_ENV", "").strip().lower() == "development"
    )

class SmartScraper:
    """
    A smart scraper that attempts a static request first and falls back
    to a dynamic (Selenium) request if the content seems insufficient.
    """
    # Selectors to identify that the main content has loaded.
    CONTENT_SELECTORS = [
        (By.CLASS_NAME, "quote"),
        (By.CLASS_NAME, "grant"),
        (By.TAG_NAME, "table"),
        (By.CLASS_NAME, "result-list"),
    ]

    MIN_PARAGRAPH_CHARS = 1000

    def __init__(self, url):
        self.url = url

    def _get_static_soup(self):
        """Fetches and parses content using a static request."""
        content, _ = fetch_public_html(self.url)
        return BeautifulSoup(content, "html.parser")

    def _get_dynamic_soup(self):
        """Fetches and parses content using Selenium for JS rendering."""
        if not dynamic_rendering_enabled():
            return None
        if not SELENIUM_AVAILABLE:
            return None

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        chrome_binary_path = os.getenv("CHROME_BIN")
        if chrome_binary_path:
            options.binary_location = chrome_binary_path

        service = Service(CHROMEDRIVER_PATH) if CHROMEDRIVER_PATH else None
        driver = None
        try:
            if service:
                driver = webdriver.Chrome(service=service, options=options)
            else:
                driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(20)
            driver.get(self.url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            try:
                WebDriverWait(driver, 10).until(
                    lambda current_driver: self._is_content_sufficient(
                        BeautifulSoup(current_driver.page_source, "html.parser")
                    )
                )
            except TimeoutException:
                pass
            html = driver.page_source
            if len(html.encode("utf-8")) > MAX_RESPONSE_BYTES:
                return None
            return BeautifulSoup(html, 'html.parser')
        except Exception:
            return None
        finally:
            if driver:
                driver.quit()

    def _is_content_sufficient(self, soup):
        """Validates if the soup object contains meaningful content."""
        if not soup:
            return False
            
        text_size = len(soup.get_text(strip=True))
        # Check for class-based selectors
        has_content_tag = any(soup.find(attrs={'class': class_}) for by_type, class_ in self.CONTENT_SELECTORS if by_type == By.CLASS_NAME)
        # Check for tag-based selectors
        has_content_tag = has_content_tag or any(soup.find(tag_name) for by_type, tag_name in self.CONTENT_SELECTORS if by_type == By.TAG_NAME)

        if has_content_tag and text_size > 1000:
            return True
        # Articles and docs without tables: count only paragraph text, so script-only
        # shells and pages that are mostly navigation still fall through.
        paragraph_size = sum(len(p.get_text(strip=True)) for p in soup.find_all("p"))
        return paragraph_size >= self.MIN_PARAGRAPH_CHARS

    def _clean_soup(self, soup):
        """Removes non-content tags from the parsed document."""
        if not soup:
            return None
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            tag.decompose()
        
        return soup

    def get_soup(self):
        """
        Main entry point to get soup. Tries static, then falls back to dynamic.
        """
        soup = self._get_static_soup()

        if not self._is_content_sufficient(soup):
            dynamic_soup = self._get_dynamic_soup()
            if dynamic_soup:
                soup = dynamic_soup
            else:
                pass

        return self._clean_soup(soup)

# Entry point for external calls, maintaining original function signature
def get_soup(url):
    scraper = SmartScraper(url)
    return scraper.get_soup()


def validate_soup(soup, url=None):
    scraper = SmartScraper(url or "")
    return scraper._is_content_sufficient(soup)
