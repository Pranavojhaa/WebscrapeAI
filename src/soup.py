from bs4 import BeautifulSoup
from network import fetch_public_html

def fetch_page(url):
    content, _ = fetch_public_html(url)
    return BeautifulSoup(content, "html.parser")



