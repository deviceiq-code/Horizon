"""Access to the internet for the app: image search on SearXNG and safe download of images.

The download only goes to public addresses (never the local network: the URL comes from users
or search results), checks every redirect, stops at a size limit and only accepts real images
(checked by their first bytes, not by what the site says).
"""

import http.client
import ipaddress
import json
import socket
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlencode, urljoin, urlsplit

USER_AGENT = "Horizon/1.0 (+asset photo search)"
TIMEOUT = 15
MAX_REDIRECTS = 3
IMAGE_TYPES = {"jpg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}


class WebError(Exception):
    """`code`: invalid_url, blocked_address, unreachable, http_error, not_image, too_large,
    json_disabled, bad_response."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


# --- Pure helpers ---------------------------------------------------------------------------


def is_public_address(ip: str) -> bool:
    """True for internet addresses; False for private, loopback, link-local, reserved…"""
    address = ipaddress.ip_address(ip)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_global and not address.is_multicast


def sniff_image(data: bytes) -> str | None:
    """The image type from the first bytes ("jpg", "png", "gif", "webp"), None otherwise."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def http_url(value: str | None) -> str | None:
    """`value` as an absolute http(s) URL ("//host/x" becomes https), None when it is not one."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if value.startswith("//"):
        value = "https:" + value
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    return value


def parse_image_results(data: object, limit: int = 24) -> list[dict]:
    """Image results of a SearXNG JSON response: image and thumbnail URLs, title, the page it
    was found on and its size, without duplicates."""
    results = data.get("results", []) if isinstance(data, dict) else []
    found, seen = [], set()
    for item in results:
        if not isinstance(item, dict):
            continue
        image = http_url(item.get("img_src"))
        if image is None or image in seen:
            continue
        seen.add(image)
        found.append(
            {
                "image": image,
                "thumbnail": http_url(item.get("thumbnail_src")) or image,
                "title": " ".join(str(item.get("title") or "").split())[:200],
                "source": http_url(item.get("url")) or "",
                "resolution": str(item.get("resolution") or "")[:20],
            }
        )
        if len(found) >= limit:
            break
    return found


# --- SearXNG --------------------------------------------------------------------------------


def search_images(base_url: str, query: str, limit: int = 24, timeout: int = TIMEOUT):
    """Images found by the SearXNG instance at `base_url` (set by an administrator, so it may
    be on the local network)."""
    params = urlencode({"q": query, "categories": "images", "format": "json", "safesearch": 1})
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/search?{params}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(5 * 1024 * 1024)
    except urllib.error.HTTPError as exc:
        # SearXNG answers 403 when the JSON format is not enabled in its settings.yml
        raise WebError("json_disabled" if exc.code == 403 else "http_error", str(exc)) from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise WebError("unreachable", str(exc)) from exc
    try:
        data = json.loads(body)
    except ValueError as exc:
        raise WebError("bad_response", "not JSON") from exc
    return parse_image_results(data, limit)


# --- Safe image download --------------------------------------------------------------------


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """Connects to the address already checked (not a new DNS lookup)."""

    def __init__(self, host, port, ip, timeout):
        super().__init__(host, port, timeout=timeout)
        self._ip = ip

    def connect(self):
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, port, ip, timeout):
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self._ip = ip

    def connect(self):
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _resolve(host: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as exc:
        raise WebError("unreachable", f"cannot resolve {host}") from exc
    return list(dict.fromkeys(info[4][0] for info in infos))


def fetch_image(
    url: str,
    max_bytes: int,
    *,
    timeout: int = TIMEOUT,
    allow_private: bool = False,
) -> tuple[bytes, str, str]:
    """Download an image. Returns (bytes, type, final URL); raises WebError."""
    current = http_url(url)
    if current is None:
        raise WebError("invalid_url")
    for _hop in range(MAX_REDIRECTS + 1):
        parts = urlsplit(current)
        secure = parts.scheme == "https"
        port = parts.port or (443 if secure else 80)
        addresses = _resolve(parts.hostname, port)
        if not allow_private and not all(is_public_address(ip) for ip in addresses):
            raise WebError("blocked_address", parts.hostname)
        connection_class = _PinnedHTTPSConnection if secure else _PinnedHTTPConnection
        connection = connection_class(parts.hostname, port, addresses[0], timeout)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        try:
            connection.request(
                "GET",
                path,
                headers={"User-Agent": USER_AGENT, "Accept": "image/*", "Host": parts.netloc},
            )
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location:
                    raise WebError("http_error", f"redirect without location ({response.status})")
                current = http_url(urljoin(current, location))
                if current is None:
                    raise WebError("invalid_url", "redirect to an unsupported address")
                continue
            if response.status != 200:
                raise WebError("http_error", str(response.status))
            length = response.getheader("Content-Length")
            if length and length.isdigit() and int(length) > max_bytes:
                raise WebError("too_large")
            data = response.read(max_bytes + 1)
        except (OSError, http.client.HTTPException) as exc:
            raise WebError("unreachable", str(exc)) from exc
        finally:
            connection.close()
        if len(data) > max_bytes:
            raise WebError("too_large")
        kind = sniff_image(data)
        if kind is None:
            raise WebError("not_image")
        return data, kind, current
    raise WebError("http_error", "too many redirects")
