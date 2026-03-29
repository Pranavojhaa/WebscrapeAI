import os
import sys
from typing import Any

import pandas as pd
from flask import Flask, render_template, request

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from inspector import fetch_count, get_element_data
from smart_scrapper import get_soup, validate_soup


app = Flask(__name__, template_folder="templates", static_folder="static")

ELEMENT_OPTIONS = {
    "paragraphs": "Paragraphs",
    "headings": "Headings",
    "images": "Images",
    "links": "Links",
    "quotes": "Quotes",
    "table": "Tables",
}


def normalize_url(url: str) -> str:
    cleaned = url.strip()
    if cleaned and not cleaned.startswith(("http://", "https://")):
        return f"https://{cleaned}"
    return cleaned


def build_result_context(result: Any, selected_element: str, selected_label: str) -> dict[str, Any]:
    context: dict[str, Any] = {
        "label": selected_label,
        "count": 0,
        "kind": "empty",
        "headers": [],
        "rows": [],
        "items": [],
    }

    if result is None:
        return context

    if isinstance(result, pd.DataFrame):
        headers = [str(column) for column in result.columns.tolist()]
        rows = result.fillna("").values.tolist()
        context.update(
            {
                "count": len(rows),
                "kind": "table",
                "headers": headers,
                "rows": rows,
            }
        )
        return context

    if selected_element == "links":
        items = [
            {"text": item.get("text", ""), "href": item.get("href", "")}
            for item in result
        ]
        context.update(
            {
                "count": len(items),
                "kind": "links",
                "items": items,
            }
        )
        return context

    items = [{"content": str(item)} for item in result]
    context.update(
        {
            "count": len(items),
            "kind": "list",
            "items": items,
        }
    )
    return context


@app.route("/", methods=["GET", "POST"])
def index():
    page_data: dict[str, Any] = {
        "url": "",
        "selected_element": "paragraphs",
        "selected_label": ELEMENT_OPTIONS["paragraphs"],
        "table_index": 1,
        "summary": None,
        "result": None,
        "error": None,
        "validated": False,
    }

    if request.method == "POST":
        raw_url = request.form.get("url", "")
        selected_element = request.form.get("element", "paragraphs")
        selected_label = ELEMENT_OPTIONS.get(selected_element, "Paragraphs")
        table_index = request.form.get("table_index", "1")

        page_data.update(
            {
                "url": raw_url,
                "selected_element": selected_element,
                "selected_label": selected_label,
                "table_index": table_index,
            }
        )

        try:
            table_number = max(int(table_index), 1)
        except ValueError:
            table_number = 1
            page_data["table_index"] = "1"

        normalized_url = normalize_url(raw_url)
        if not normalized_url:
            page_data["error"] = "Enter a URL to inspect."
            return render_template("index.html", element_options=ELEMENT_OPTIONS, **page_data)

        try:
            soup = get_soup(normalized_url)
            if not validate_soup(soup, normalized_url):
                page_data["error"] = "This page does not look rich enough for meaningful scraping."
                return render_template("index.html", element_options=ELEMENT_OPTIONS, **page_data)

            page_data["validated"] = True
            page_data["url"] = normalized_url
            page_data["summary"] = fetch_count(soup)
            result = get_element_data(soup, selected_element, table_index=table_number - 1)
            page_data["result"] = build_result_context(result, selected_element, selected_label)
        except Exception as exc:
            page_data["error"] = f"Could not inspect the page: {exc}"

    return render_template("index.html", element_options=ELEMENT_OPTIONS, **page_data)


@app.get("/health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
