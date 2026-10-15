# SQL_INJECTION Security Report

## Status: No injection found in current account-store queries; hosted verification pending

## Findings

The private account store now uses SQLite locally and PostgreSQL in production. SQL statements are fixed strings and user-provided email values are bound parameters. The only dialect adaptation changes static `%s` placeholders to SQLite `?` placeholders; input values are not interpolated into SQL.

## What's at risk

The database has not been provisioned or tested on Render. Future query changes must preserve parameter binding.

## What's already secure

- Login, account creation, account listing, and enable/disable operations use parameterized statements.
- The public demo does not open a database connection.

## Recommendations

1. Keep user-provided values parameterized.
2. Run the account-store tests on every change and exercise PostgreSQL behavior in staging.
