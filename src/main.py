from smart_scrapper import get_soup,validate_soup
from inspector import fetch_page, inspect_element

def main():
    print("🌐 Welcome to WebScrapeAI!")
    print("This tool lets you inspect, scrape, and analyze data from any webpage.\n")

    url = input("🔗 Enter the URL of the website you want to scrape: ").strip()
    if not url.startswith("http"):
        url = "https://" + url

    soup = get_soup(url)
    validation = validate_soup(soup, url)

    if validation == "retry":
        print("\n🔁 Retrying with Selenium...")
        soup = get_soup(url)  # this will trigger the Selenium path
        validation = validate_soup(soup, url)

    if validation is False:
        print("❌ Page is not suitable for scraping. Exiting.")
        return
    # Show what elements are available
    data = fetch_page(url)
    print("\n🔍 Elements detected on page:")
    for index, (key, value) in enumerate(data.items()):
        print(f"{index}: {key} → {value}")

    # Hand control to interactive inspector
    inspect_element(url)

    print("\n👋 Exiting WebScrapeAI. Thanks for scraping!")

if __name__ == "__main__":
    main()
