# ACCESS_CONTROL Security Report

## Status: N/A

## Findings

No route takes a resource ID and there are no per-user resources. Production uses one shared credential, so there is no ownership to check. `table_index` selects a table inside the page just fetched and is bounds-checked in `inspector.get_element_data`.

## What's at risk

Nothing.

## What's already secure

Not applicable.

## Recommendations

Revisit if user accounts or saved results are added.
