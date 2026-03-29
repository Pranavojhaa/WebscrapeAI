# AutoScrapeAI

AutoScrapeAI is a lightweight scraping workspace with a basic HTML and CSS frontend for quickly inspecting the shape of a webpage before you commit to deeper extraction.

It is built for the moment right after "can I scrape this page?" and right before "what exactly should I extract?"

## What It Does

- Fetches a page with a static request first for speed.
- Falls back to Selenium-based rendering when the page looks too thin.
- Cleans the DOM and inspects useful element groups like tables, headings, links, images, quotes, and paragraphs.
- Presents results in a more analyst-friendly UI instead of raw HTML noise.

## Experience

The web app is intentionally simple:

- A basic form for entering a URL and choosing what to inspect.
- A summary section showing what kinds of content were found.
- Plain result views for tables, links, images, quotes, headings, and paragraphs.
- Lightweight CSS for a clean layout without a heavy frontend framework.

## Project Layout

```text
src/
  app.py              Flask app
  main.py             CLI entry point
  smart_scrapper.py   Fetching, validation, dynamic fallback
  inspector.py        Element counting and inspection helpers
  scraper.py          Lower-level scraping functions
  exporter.py         Export helpers
  analyzer.py         Optional AI analysis flow
  soup.py             Basic soup fetch helper
```

## Run It

Install dependencies:

```bash
pip install -r requirements.txt
```

Launch the web app:

```bash
python3 src/app.py
```

Run the CLI version:

```bash
python3 src/main.py
```

## Notes

- If Selenium is not installed or unavailable, the app still loads and continues with standard HTTP scraping.
- Some pages may still require a working ChromeDriver setup for dynamic rendering.
- Exported artifacts and debug HTML may be generated in the project root during use.

## Next Nice Upgrades

- In-app export controls for every inspection mode.
- Async loading states for slower pages.
- Better dynamic-site heuristics and richer table selection.
