import pandas as pd

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
    return [{'text': a.text.strip(), 'href': a['href']} for a in soup.find_all('a') if 'href' in a.attrs]

def scrape_quotes(soup):
    quotes = soup.find_all("div", class_="quote")
    return [
        f'{q.find("span", class_="text").text.strip()} — {q.find("small", class_="author").text.strip()}'
        for q in quotes
    ]
