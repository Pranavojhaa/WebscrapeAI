# ACCESS_CONTROL Fix Plan

## Changes

- Add persistent member accounts, active/admin roles, and administrator-managed create/disable/enable actions.
- Keep account management private to admins and use CSRF-protected POSTs for state changes.
- Keep the public demo on a separate entry point with no account or scraper access.

## Verification goals

- [x] Member sessions require active accounts.
- [x] Non-admins cannot use `/admin/users`.
- [x] The last active admin cannot be disabled.
- [x] Demo routes accept only catalog fixture IDs.
- [ ] Verify the two Render environments remain isolated after provisioning.

## Manual verification

- Test member creation, disablement, and re-enablement before inviting users.
- Add password rotation/reset before wider access.
