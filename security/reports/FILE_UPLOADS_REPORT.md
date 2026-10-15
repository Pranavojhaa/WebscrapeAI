# FILE_UPLOADS Security Report

## Status: N/A

## Findings

There are no upload endpoints. `MAX_CONTENT_LENGTH` is 32 KB, so large bodies are rejected. Exports are generated in memory and never written to disk by the web app (the CLI's `src/exporter.py` writes fixed filenames in the working directory, locally only).

## What's at risk

Nothing.

## What's already secure

Not applicable.

## Recommendations

None.
