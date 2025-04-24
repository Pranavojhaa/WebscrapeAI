import requests
from bs4 import BeautifulSoup
from scraper import scrape_table,scrape_headings,scrape_images,scrape_links,scrape_paragraphs

def fetch_page(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    table = 0 
    paragraphs = 0
    headings = 0
    images = 0
    links = 0
    # Initialize counters for different HTML elements
    if soup.find_all('table'):
        table = len(soup.find_all('table'))
    if soup.find_all('p'):
        paragraphs = len(soup.find_all('p'))
    if soup.find_all(['h1','h2','h3','h4','h5','h6']):
        headings = len(soup.find_all(['h1','h2','h3','h4','h5','h6']))
    if soup.find_all('img'):
        images = len(soup.find_all('img'))
    if soup.find_all('a'):
        links = len(soup.find_all('a'))
    return {
        'table': table,
        'paragraphs': paragraphs,
        'headings': headings,
        'images': images,
        'links': links
    }

def inspect_element(url):
    while True:
        check = input("\nWhat do you want to inspect (table, paragraphs, headings, images, links) or Exit: ").strip().lower()

        if check == 'table':
            table_df = scrape_table(url)
            if table_df is not None:
                print(table_df.head())
        elif check == 'paragraphs':
            paras = scrape_paragraphs(url)
            print(f"\nFound {len(paras)} paragraphs. Preview:\n", paras[0][:300] if paras else "None")
        elif check == 'headings':
            headings = scrape_headings(url)
            print(f"\nHeadings Found ({len(headings)}):\n", headings[:5])
        elif check == 'images':
            images = scrape_images(url)
            print(f"\nFound {len(images)} images. Preview:\n", images[:5])
        elif check == 'links':
            links = scrape_links(url)
            print(f"\nFound {len(links)} links. Preview:\n", links[:5])
        elif check == 'exit':
            break
        else:
            print("❌ Invalid option. Try again.")
            continue

        processing = input(
            "\nWhat do you want to do now?\n"
            "1. Inspect another element\n"
            "2. Export this element\n"
            "3. AI Analysis\n"
            "4. Exit\n"
            "Enter your choice (1/2/3/4): "
        )

        if processing == '1':
            continue
        elif processing == '2':
            print("🚧 Export feature coming soon...")
            # Call exporter module here
        elif processing == '3':
            print("🚧 AI analysis feature coming soon...")
            # Call analyzer module here
        elif processing == '4':
            print("👋 Exiting inspection.")
            break
        else:
            print("❌ Invalid choice. Returning to main inspection.") 



if __name__ == "__main__":
    url = "https://en.wikipedia.org/wiki/List_of_largest_companies_in_the_United_States_by_revenue"
    summary = fetch_page(url)
    print("\n🔍 Website Inspection Result:")
    for k, v in summary.items():
        print(f"{k.capitalize()}: {v}")



