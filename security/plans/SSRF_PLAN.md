# SSRF Fix Plan

## Changes

- `src/network.py` — new `resolve_public_address()`; `_PinnedAdapter` and connection classes resolve, check and connect in one step, restoring the hostname before the TLS handshake so SNI and certificate checks are unchanged; `MAX_FETCH_SECONDS = 30` deadline in the read loop.

## New files

- `tests/test_security.py` — `test_dns_rebinding_is_blocked_at_connect_time`, `test_connection_is_made_to_the_validated_address`.

## Verification goals

- [x] All user-supplied fetching validates the URL first
- [x] Private, loopback, link-local and reserved ranges are blocked (live probes)
- [x] Only http and https are allowed
- [x] The address checked is the address connected to (test simulates a public-then-private DNS answer; no connection is attempted)
- [x] Real HTTPS fetches still work and a certificate hostname mismatch is still rejected (checked against `example.com` and `wrong.host.badssl.com`)

## Manual verification (for the human)

- The pinning relies on urllib3 internals (`_new_conn`, `_dns_host`), verified on urllib3 2.8.0. `urllib3` is not pinned in `requirements.txt`; the two tests above will fail if an upgrade changes those internals.
- Add outbound destination restrictions at the network layer on the selected host or an egress proxy.
