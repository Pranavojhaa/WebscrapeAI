import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time

CHROMEDRIVER_PATH = "/Users/pranavojha/AutoScrapeAI/src/chromedriver"

def validate_soup(soup, url=""):
    tag_count = len(soup.find_all())
    text_size = len(soup.get_text(strip=True))

    # ✅ Check if table or grant results exist
    has_grants = soup.find("table") or soup.find(class_="result-list") or soup.find_all("div", class_="grant")

    if not has_grants or tag_count < 50 or text_size < 1000:
        print(f"\n⚠️ WARNING: The page at {url} appears to have minimal usable content.")
        print("🔎 It likely requires JavaScript to load key data (e.g., grants, listings).")
        choice = input("👉 Retry with Selenium rendering? (y/n): ").strip().lower()
        return "retry" if choice == 'y' else False

    return True


def is_dynamic_site(url):
    try:
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.content, 'html.parser')
        text = soup.get_text(strip=True)
        links = soup.find_all('a')
        return len(text) < 1000 or len(links) < 5
    except Exception:
        return True

def get_dynamic_soup(url):
    print("⚙️ Using Selenium to render full page (dynamic content)...")

    options = Options()
    options.headless = True
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    driver.get(url)
    time.sleep(5)  # Let JS fully load

    rendered_html = driver.page_source
    driver.quit()

    soup = BeautifulSoup(rendered_html, 'html.parser')

    # Optional cleanup: remove JSON script blobs
    for script in soup(["script", "style", "noscript"]):
        script.extract()

    return soup

def get_static_soup(url):
    print("📄 Using static requests + BeautifulSoup...")
    response = requests.get(url)
    return BeautifulSoup(response.content, 'html.parser')

def get_soup(url):
    if is_dynamic_site(url):
        use_selenium = input("⚠️ This site looks dynamic. Use Selenium to render JavaScript? (y/n): ").strip().lower()
        return get_dynamic_soup(url) if use_selenium == 'y' else get_static_soup(url)
    return get_static_soup(url)
