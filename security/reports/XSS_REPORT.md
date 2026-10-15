# XSS Security Report

## Status: LOW (fixed)

## Findings

All scraped content and the AI analysis are rendered through Jinja with autoescaping on (`.html` template, no `|safe`, no `Markup`). There is no JavaScript. The CSP has no `unsafe-inline`, which also blocks `javascript:` navigation.

- **LOW — scraped `href` used as a link without a scheme check.** `src/templates/index.html` rendered `<a href="{{ item.href }}" target="_blank">` for every scraped link, including `javascript:` and `data:` URLs. The CSP stops `javascript:` from executing, so this was a missing second layer, not a working exploit. Relative hrefs also resolved against this app's own origin.
- **LOW — spreadsheet formula injection in exports.** Table cells are scraped from untrusted pages and written unchanged to CSV and XLSX. A cell such as `=HYPERLINK(...)` becomes a live formula when the file is opened; `openpyxl` stores any string starting with `=` as a formula.

## What's at risk

A malicious page could plant a link that runs script if the CSP were ever loosened, or a formula that runs when the user opens an exported sheet.

## What's already secure

Autoescaping, strict CSP, `rel="noreferrer"` on outbound links, downloads sent as attachments with a fixed filename pattern and `nosniff`. The export filename uses `selected_element` only after it is checked against the allowlist.

## Recommendations

1. Render an anchor only for `http://` and `https://` hrefs (done).
2. Prefix formula-leading cells with `'` in CSV and XLSX exports, leaving plain numbers such as `-5.2` alone (done). JSON exports are unchanged.
