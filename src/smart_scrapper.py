import requests
from bs4 import BeautifulSoup

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    webdriver = None
    Options = None
    Service = None
    WebDriverWait = None
    EC = None
    SELENIUM_AVAILABLE = False

    class By:
        CLASS_NAME = "class name"
        TAG_NAME = "tag name"

CHROMEDRIVER_PATH = "/Users/pranavojha/AutoScrapeAI/src/chromedriver"

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

    def __init__(self, url):
        self.url = url

    def _get_static_soup(self):
        """Fetches and parses content using a static request."""
        print("📄 Using static requests + BeautifulSoup...")
        try:
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            print(f"❌ Failed to fetch static content: {e}")
            return None

    def _get_dynamic_soup(self):
        """Fetches and parses content using Selenium for JS rendering."""
        print("⚙️ Using Selenium to render full page (dynamic content)...")
        if not SELENIUM_AVAILABLE:
            print("⚠️ Selenium is not installed. Skipping dynamic rendering.")
            return None

        options = Options()
        options.headless = True
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        service = Service(CHROMEDRIVER_PATH)
        driver = None
        try:
            driver = webdriver.Chrome(service=service, options=options)
            driver.get(self.url)
            
            # Wait for any of the key content selectors to appear
            wait_conditions = [EC.presence_of_element_located(s) for s in self.CONTENT_SELECTORS]
            WebDriverWait(driver, 15).until(EC.any_of(*wait_conditions))
            
            print("✅ JS content loaded successfully.")
            html = driver.page_source
            return BeautifulSoup(html, 'html.parser')
        except Exception as e:
            print(f"⚠️ Timeout or error waiting for dynamic content: {e}")
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

        return has_content_tag and text_size > 1000

    def _clean_soup(self, soup):
        """Removes script/style tags and saves a debug file."""
        if not soup:
            return None
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            tag.decompose()
        
        # Optional: save HTML for debugging
        with open("soup_debug.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        print("🔎 Dumped cleaned soup to soup_debug.html")
        return soup

    def get_soup(self):
        """
        Main entry point to get soup. Tries static, then falls back to dynamic.
        """
        soup = self._get_static_soup()

        if not self._is_content_sufficient(soup):
            print(f"\n⚠️ WARNING: The page at {self.url} appears to have minimal content.")
            print("   Retrying with Selenium for dynamic content.")
            dynamic_soup = self._get_dynamic_soup()
            if dynamic_soup:
                soup = dynamic_soup
            else:
                print("ℹ️ Proceeding with the best available content.")

        return self._clean_soup(soup)

# Entry point for external calls, maintaining original function signature
def get_soup(url):
    scraper = SmartScraper(url)
    return scraper.get_soup()


def validate_soup(soup, url=None):
    scraper = SmartScraper(url or "")
    return scraper._is_content_sufficient(soup)

# Example usage:
if __name__ == '__main__':
    # URL that likely needs JS
    # test_url = "http://quotes.toscrape.com/js/" 
    
    # URL that works statically
    test_url = "http://quotes.toscrape.com/"

    final_soup = get_soup(test_url)

    if final_soup:
        print("\n✅ Scraping finished. Final soup object is ready.")
        # print(final_soup.prettify()[:500]) # Print first 500 chars
    else:
        print("\n❌ Scraping failed to retrieve usable content.")
