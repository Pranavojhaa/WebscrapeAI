import requests
from bs4 import BeautifulSoup
import pandas as pd
from soup import fetch_page

def scrape_table(soup):
    tables = soup.find_all('table')
    if not tables:
        print("No tables found.")
        return None

    table_no = int(input(f"Enter the table you want to check from 1 to {len(tables)}: "))
    selected_table = tables[table_no - 1]

    rows = selected_table.find_all('tr')
    data = []

    for row in rows:
        cols = [td.text.strip() for td in row.find_all(['td', 'th'])]
        if len(cols) > 0:
            data.append(cols)

    df = pd.DataFrame(data)
    return df



def scrape_paragraphs(soup):
    return [p.text.strip() for p in soup.find_all('p')]

def scrape_headings(soup):
    return [h.text.strip() for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])]

def scrape_images(soup):
    return [img['src'] for img in soup.find_all('img') if 'src' in img.attrs]

def scrape_links(soup):
    links = [{'text': a.text.strip(), 'href': a['href']} for a in soup.find_all('a') if 'href' in a.attrs]

    for index, link in enumerate(links):
        print(f"[{index + 1}] Text: {link['text']} | URL: {link['href']}")
    
    return links

def scrape_quotes(soup):
    quotes = soup.find_all("div", class_="quote")
    return [
        f'{q.find("span", class_="text").text.strip()} — {q.find("small", class_="author").text.strip()}'
        for q in quotes
    ]




if __name__ == "__main__":
    url = "https://en.wikipedia.org/wiki/List_of_largest_companies_in_the_United_States_by_revenue"
    print(f"\n🌐 Scraping URL: {url}")
    url = fetch_page(url)

    print("\n🧾 Scraping Tables...")
    df = scrape_table(url)
    if df is not None:
        print("\n📊 Sample Table Data:")
        print(df.head())
    else:
        print("❌ No tables extracted.")

    print("\n📄 Scraping Paragraphs...")
    paragraphs = scrape_paragraphs(url)
    print(f"✅ {len(paragraphs)} paragraphs found.")
    print("\n📝 Sample Paragraph:")
    print(paragraphs if paragraphs else "No paragraph content found.")

    print("\n🔠 Scraping Headings...")
    headings = scrape_headings(url)
    print(f"✅ {len(headings)} headings found.")
    print("\n🔤 Sample Headings:")
    print(headings if headings else "No headings found.")

    print("\n🖼️ Scraping Images...")
    images = scrape_images(url)
    print(f"✅ {len(images)} image sources found.")
    print("\n📷 Sample Image URLs:")
    print(images if images else "No images found.")

    print("\n🔗 Scraping Links...")
    links = scrape_links(url)
    print(f"✅ {len(links)} links found.")
    print("\n🔗 Sample Links:")
    for link in links[:5]:
        print(f"- {link['text']}: {link['href']}")
    print("\n✅ Scraping Completed!")
