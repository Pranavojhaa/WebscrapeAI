# SQL_INJECTION Fix Plan

## Changes

- Add database-backed account operations with parameterized SQL for SQLite and PostgreSQL.

## Verification goals

- [x] No user-controlled strings are interpolated into SQL.
- [x] Account-store regression tests cover authentication and lifecycle operations.
- [ ] Exercise PostgreSQL queries in Render staging.

## Manual verification

- Preserve parameter binding for any future database query.
