import requests
from bs4 import BeautifulSoup

def fetch_page(url):
    response = requests.get(url)
    return  BeautifulSoup(response.content, 'html.parser') 




