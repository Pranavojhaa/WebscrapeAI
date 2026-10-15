# ERROR_HANDLING Fix Plan

## Changes

- `src/app.py` — `except requests.RequestException` branch with the generic message.
- `src/network.py` — `content_length.isdigit()` guard.

## New files

None.

## Verification goals

- [x] Client responses contain only app-authored or generic messages
- [x] Full details are logged server-side only
- [x] Debug mode is off
- [x] No API docs or debug endpoints (live, local)
- [ ] `Server` header on the deployed app does not disclose versions (not checked)

## Manual verification (for the human)

- Check the `Server` header on the Railway URL.
