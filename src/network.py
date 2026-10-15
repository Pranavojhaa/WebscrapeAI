import ipaddress
import socket
import time
from urllib.parse import urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool


MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_FETCH_SECONDS = 30
MAX_REDIRECTS = 5
REQUEST_TIMEOUT = (5, 15)
REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class URLSafetyError(ValueError):
    pass


def validate_public_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise URLSafetyError("Enter a valid public HTTP or HTTPS URL.") from exc

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise URLSafetyError("Only public HTTP and HTTPS URLs can be inspected.")
    expected_port = 443 if parsed.scheme == "https" else 80
    if port is not None and port != expected_port:
        raise URLSafetyError("Only standard HTTP and HTTPS ports can be inspected.")
    if parsed.username or parsed.password:
        raise URLSafetyError("URLs containing user information are not supported.")

    resolve_public_address(parsed.hostname, expected_port)
    return url


def resolve_public_address(hostname: str, port: int) -> str:
    hostname = hostname.rstrip(".")
    try:
        addresses = [ipaddress.ip_address(hostname)]
    except ValueError:
        try:
            records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except (socket.gaierror, UnicodeError) as exc:
            raise URLSafetyError("The website hostname could not be resolved.") from exc
        addresses = [ipaddress.ip_address(record[4][0].split("%", 1)[0]) for record in records]

    if not addresses or any(not address.is_global for address in addresses):
        raise URLSafetyError("Private, local, or reserved network addresses are blocked.")

    return str(addresses[0])


class _PinnedConnectionMixin:
    # Resolve, check and connect in one step, so a DNS answer that changes after
    # validate_public_url (DNS rebinding) cannot point the socket at a private address.
    # The hostname is restored before the TLS handshake, so SNI and certificate checks still use it.
    def _new_conn(self):
        hostname = self._dns_host
        self._dns_host = resolve_public_address(hostname, self.port)
        try:
            return super()._new_conn()
        finally:
            self._dns_host = hostname


class _PinnedHTTPConnection(_PinnedConnectionMixin, HTTPConnection):
    pass


class _PinnedHTTPSConnection(_PinnedConnectionMixin, HTTPSConnection):
    pass


class _PinnedHTTPPool(HTTPConnectionPool):
    ConnectionCls = _PinnedHTTPConnection


class _PinnedHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = _PinnedHTTPSConnection


class _PinnedAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {"http": _PinnedHTTPPool, "https": _PinnedHTTPSPool}


def fetch_public_html(url: str) -> tuple[bytes, str]:
    current_url = url
    session = requests.Session()
    session.trust_env = False
    session.mount("http://", _PinnedAdapter())
    session.mount("https://", _PinnedAdapter())
    # The read timeout is per chunk; this caps the whole fetch so a slow-drip server cannot hold a worker.
    deadline = time.monotonic() + MAX_FETCH_SECONDS

    try:
        for redirect_count in range(MAX_REDIRECTS + 1):
            validate_public_url(current_url)
            response = session.get(
                current_url,
                allow_redirects=False,
                headers={"User-Agent": "WebScrapeAI/1.0"},
                stream=True,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code in REDIRECT_STATUSES:
                location = response.headers.get("Location")
                response.close()
                if not location:
                    raise URLSafetyError("The website returned an invalid redirect.")
                if redirect_count == MAX_REDIRECTS:
                    raise URLSafetyError("The website redirected too many times.")
                current_url = urljoin(current_url, location)
                continue

            try:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").lower()
                if content_type and not any(kind in content_type for kind in ("text/html", "application/xhtml+xml")):
                    raise URLSafetyError("The URL did not return an HTML page.")

                content_length = response.headers.get("Content-Length")
                if content_length and content_length.isdigit() and int(content_length) > MAX_RESPONSE_BYTES:
                    raise URLSafetyError("The page is too large to inspect (5 MB maximum).")

                content = bytearray()
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    content.extend(chunk)
                    if time.monotonic() > deadline:
                        raise URLSafetyError("The page took too long to download.")
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise URLSafetyError("The page is too large to inspect (5 MB maximum).")

                return bytes(content), current_url
            finally:
                response.close()

        raise URLSafetyError("The website redirected too many times.")
    finally:
        session.close()
