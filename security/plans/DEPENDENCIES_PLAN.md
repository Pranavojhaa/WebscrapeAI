# DEPENDENCIES Fix Plan

## Changes

- `requirements.txt` — now a generated, hashed lock of every runtime package. Its header shows the regeneration command.
- `requirements-selenium.txt` — same, for the runtime set plus Selenium.
- `README.md` — explains the `.in` → `.txt` workflow.

## New files

- `requirements.in` — the 8 direct runtime pins (previously in `requirements.txt`).
- `requirements-selenium.in` — `-r requirements.in` plus `selenium==4.51.0`.

## Verification goals

- [x] Every dependency, direct and transitive, is pinned exactly
- [x] Every pin carries hashes; `pip install --require-hashes -r requirements.txt` succeeds (fresh venv, Python 3.14, macOS)
- [x] Lock files are in the repo (untracked until committed)
- [x] No known vulnerabilities in any pinned version (OSV, 52 versions)
- [ ] CI `dependency-audit` and `unit-tests` jobs pass on Linux with Python 3.11 and 3.12 (not run)

## Manual verification (for the human)

- To change a dependency, edit the `.in` file, run the command in the lock file's header, and commit both files. `uv` is needed for this (`pip install uv` or `brew install uv`).
- Watch the first hosted build to confirm it installs from the lock without errors.
