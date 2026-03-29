from smart_scrapper import get_soup
from inspector import inspect_element, fetch_count


def main():
    print("🌐 Welcome to WebScrapeAI!")
    print("This tool lets you inspect, scrape, and analyze data from any webpage.\n")

    url = input("🔗 Enter the URL of the website you want to scrape: ").strip()
    if not url:
        print("❌ URL cannot be empty. Exiting.")
        return
    if not url.startswith("http"):
        url = "https://" + url

    # Step 1: Fetch soup using the smart scraper
    # The get_soup function now handles static/dynamic fetching and validation internally.
    soup = get_soup(url)

    if not soup:
        print("❌ Failed to fetch the page or content is insufficient. Please check the URL and try again.")
        return
    
    print("\n✅ Scraping Completed!")

    # Step 2: Count elements
    data = fetch_count(soup)
    print("\n🔍 Elements detected on page:")
    for index, (key, value) in enumerate(data.items()):
        print(f"{index}: {key.capitalize()} → {value}")

    # Step 3: Inspect elements
    inspect_element(soup)

    print("\n👋 Exiting WebScrapeAI. Thanks for scraping!")


if __name__ == "__main__":
    main()
