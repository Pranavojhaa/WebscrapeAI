from scraper import scrape_table, scrape_headings, scrape_images, scrape_links, scrape_paragraphs, scrape_quotes
from exporter import export_table, export_text_data, export_links, export_images


def fetch_count(soup):
    table = len(soup.find_all('table'))
    paragraphs = len(soup.find_all('p'))
    headings = len(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']))
    images = len(soup.find_all('img'))
    links = len(soup.find_all('a'))
    quotes = len(soup.find_all('div', class_='quote'))  # ✅ added dynamic quote detection

    return {
        'table': table,
        'paragraphs': paragraphs,
        'headings': headings,
        'images': images,
        'links': links,
        'quotes': quotes  
    }


def get_element_data(soup, element, table_index=0):
    element = element.lower()

    if element == "table":
        tables = soup.find_all('table')
        if not tables:
            return None
        if table_index < 0 or table_index >= len(tables):
            raise IndexError("Requested table index is out of range.")

        rows = tables[table_index].find_all('tr')
        data = []
        for row in rows:
            cols = [td.text.strip() for td in row.find_all(['td', 'th'])]
            if cols:
                data.append(cols)

        if not data:
            return None

        import pandas as pd
        return pd.DataFrame(data)

    if element == "paragraphs":
        return scrape_paragraphs(soup)
    if element == "headings":
        return scrape_headings(soup)
    if element == "images":
        return scrape_images(soup)
    if element == "links":
        return scrape_links(soup)
    if element == "quotes":
        return scrape_quotes(soup)

    raise ValueError(f"Unsupported element type: {element}")


def inspect_element(soup):
    last_selected_data = None
    last_selected_type = None

    while True:
        try:
            check = int(input("\nWhat do you want to inspect \n1.table\n2.paragraphs\n3.headings\n4.images\n5.links\n6.quotes\nExit (0): "))
        except ValueError:
            print("❌ Invalid input. Please enter a number.")
            continue

        if check == 1:
            table_df = scrape_table(soup)
            if table_df is not None:
                print(table_df.head())
                last_selected_data = table_df
                last_selected_type = 'table'
        elif check == 2:
            paras = scrape_paragraphs(soup)
            print(f"\nFound {len(paras)} paragraphs. Preview:\n", paras[0][:300] if paras else "None")
            last_selected_data = paras
            last_selected_type = 'paragraphs'
        elif check == 3:
            headings = scrape_headings(soup)
            print(f"\nHeadings Found ({len(headings)}):\n", headings[:5])
            last_selected_data = headings
            last_selected_type = 'headings'
        elif check == 4:
            images = scrape_images(soup)
            print(f"\nFound {len(images)} images. Preview:\n", images[:5])
            last_selected_data = images
            last_selected_type = 'images'
        elif check == 5:
            links = scrape_links(soup)
            print(f"\nFound {len(links)} links. Preview:\n", links[:5])
            last_selected_data = links
            last_selected_type = 'links'
        elif check == 6:
            quotes = scrape_quotes(soup)
            print(f"\nFound {len(quotes)} quotes. Preview:\n", quotes[:5] if quotes else "None")
            last_selected_data = quotes
            last_selected_type = 'quotes'
        elif check == 0:
            print("👋 Exiting inspection.")
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
            if last_selected_data is None:
                print("❌ No data to export. Please scrape something first.")
                continue

            # 🚀 Show export options based on type
            if last_selected_type == 'table':
                choice = input("Export as CSV, JSON, or Excel? (csv/json/excel): ").strip().lower()
                export_table(last_selected_data, choice)

            elif last_selected_type in ['paragraphs', 'headings', 'quotes']:
                choice = input("Export as TXT or JSON? (txt/json): ").strip().lower()
                export_text_data(last_selected_data, choice, filename=f"exported_{last_selected_type}")

            elif last_selected_type == 'images':
                export_images(last_selected_data)

            elif last_selected_type == 'links':
                export_links(last_selected_data)

        elif processing == '3':
            try:
                from analyzer import start_chat_with_data, dataframe_to_markdown, summarize_paragraphs
            except ImportError as exc:
                print(f"❌ AI analysis is unavailable: {exc}")
                continue

            data_to_analyze = ""
            if check == 1 and table_df is not None:
                data_to_analyze = dataframe_to_markdown(table_df)
            elif check == 2:
                data_to_analyze = summarize_paragraphs(paras)
            elif check == 3:
                data_to_analyze = "\n".join(headings)
            elif check == 4:
                data_to_analyze = "\n".join(images)
            elif check == 5:
                data_to_analyze = "\n".join([link['text'] + ": " + link['href'] for link in links])
            elif check == 6:
                data_to_analyze = "\n".join(quotes)
            else:
                data_to_analyze = "No data selected."

            start_chat_with_data(data_to_analyze)
        elif processing == '4':
            print("👋 Exiting inspection.")
            break
        else:
            print("❌ Invalid choice. Returning to main inspection.")
