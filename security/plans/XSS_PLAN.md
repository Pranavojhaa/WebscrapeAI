# XSS Fix Plan

## Changes

- `src/templates/index.html` — non-http(s) hrefs render as text.
- `src/app.py` — `neutralize_formula()` applied to DataFrames for `csv` and `xlsx` exports.

## New files

- `tests/test_security.py` — `test_only_http_links_are_rendered_as_anchors`, `test_formula_cells_are_neutralized_in_spreadsheet_exports`.

## Verification goals

- [x] No raw HTML rendering of scraped content; autoescaping on
- [x] `javascript:` hrefs are not emitted as links (test)
- [x] Cells starting with `=`, `+`, `-`, `@`, tab or CR are neutralized in CSV/XLSX unless they are plain numbers (test)

## Manual verification (for the human)

- Exported cells that started with a formula character now carry a leading apostrophe. Say so if you would prefer raw data and accept the risk.
