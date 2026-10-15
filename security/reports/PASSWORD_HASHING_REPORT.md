# PASSWORD_HASHING Security Report

## Status: N/A

## Findings

The app stores no passwords. The single production credential lives in the `APP_PASSWORD` environment variable and is compared in constant time. No MD5, SHA-1 or SHA-256 is used on passwords anywhere.

## What's at risk

Anyone who can read the Railway environment can read the password, as with any deploy secret.

## What's already secure

Constant-time comparison; minimum length of 16 enforced.

## Recommendations

If user accounts are ever added, use Argon2 or bcrypt.
