import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from django.contrib.auth import get_user_model

from .models import SystemSettings
from .web import (
    WebError,
    fetch_image,
    http_url,
    is_public_address,
    parse_image_results,
    search_images,
    sniff_image,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64

SEARX_RESULTS = {
    "results": [
        {
            "img_src": "https://example.com/5060e.jpg",
            "thumbnail_src": "https://example.com/5060e-small.jpg",
            "title": "John  Deere 5060E",
            "url": "https://example.com/tractors/5060e",
            "resolution": "1366 x 768",
        },
        {"img_src": "//cdn.example.com/b.png", "title": "B"},  # protocol-relative
        {"img_src": "https://example.com/5060e.jpg", "title": "duplicate"},
        {"img_src": "javascript:alert(1)", "title": "not http"},
        {"title": "no image"},
    ]
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status, body=b"", content_type="text/plain", headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/search":
            self._send(200, json.dumps(SEARX_RESULTS).encode(), "application/json")
        elif path == "/no-json/search":
            self._send(403, b"Forbidden", "text/html")
        elif path == "/img.png":
            # Wrong type on purpose: the first bytes decide
            self._send(200, PNG, "text/plain")
        elif path == "/photo%20front.jpeg":
            self._send(200, JPEG, "image/jpeg")
        elif path == "/moved":
            self._send(302, headers={"Location": "/img.png"})
        elif path == "/loop":
            self._send(302, headers={"Location": "/loop"})
        elif path == "/page.html":
            self._send(200, b"<html>not an image</html>", "text/html")
        elif path == "/big.png":
            self._send(200, PNG + b"\x00" * 5000, "image/png")
        else:
            self._send(404, b"nope")


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


# --- Pure helpers ---------------------------------------------------------------------------


def test_is_public_address():
    assert is_public_address("8.8.8.8")
    assert is_public_address("2001:4860:4860::8888")
    for private in (
        "127.0.0.1",
        "10.0.0.5",
        "192.168.0.22",
        "172.16.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",
        "::1",
        "fe80::1",
        "::ffff:192.168.0.1",
        "224.0.0.1",
    ):
        assert not is_public_address(private), private


def test_sniff_image():
    assert sniff_image(JPEG) == "jpg"
    assert sniff_image(PNG) == "png"
    assert sniff_image(b"GIF89a....") == "gif"
    assert sniff_image(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"
    assert sniff_image(b"<svg xmlns=") is None
    assert sniff_image(b"") is None


def test_http_url():
    assert http_url(" https://a.com/x ") == "https://a.com/x"
    assert http_url("//a.com/x") == "https://a.com/x"
    for bad in ("ftp://a.com", "javascript:alert(1)", "a.com/x", "", None, "http://"):
        assert http_url(bad) is None


def test_parse_image_results():
    results = parse_image_results(SEARX_RESULTS)
    assert results == [
        {
            "image": "https://example.com/5060e.jpg",
            "thumbnail": "https://example.com/5060e-small.jpg",
            "title": "John Deere 5060E",
            "source": "https://example.com/tractors/5060e",
            "resolution": "1366 x 768",
        },
        {
            "image": "https://cdn.example.com/b.png",
            "thumbnail": "https://cdn.example.com/b.png",
            "title": "B",
            "source": "",
            "resolution": "",
        },
    ]
    assert parse_image_results(SEARX_RESULTS, limit=1)[0]["title"] == "John Deere 5060E"
    assert parse_image_results("garbage") == []


# --- Network ----------------------------------------------------------------------------------


def test_search_images(server):
    assert len(search_images(server, "john deere")) == 2


def test_search_images_json_disabled(server):
    with pytest.raises(WebError) as exc:
        search_images(f"{server}/no-json", "x")
    assert exc.value.code == "json_disabled"


def test_search_images_unreachable():
    with pytest.raises(WebError) as exc:
        search_images("http://127.0.0.1:9", "x", timeout=2)
    assert exc.value.code == "unreachable"


def test_fetch_image(server):
    data, kind, final = fetch_image(f"{server}/img.png", 1000, allow_private=True)
    assert (data, kind, final) == (PNG, "png", f"{server}/img.png")
    # Redirects are followed (and checked)
    assert fetch_image(f"{server}/moved", 1000, allow_private=True)[2] == f"{server}/img.png"


@pytest.mark.parametrize(
    ("path", "code"),
    [
        ("/page.html", "not_image"),
        ("/big.png", "too_large"),
        ("/missing", "http_error"),
        ("/loop", "http_error"),
    ],
)
def test_fetch_image_errors(server, path, code):
    with pytest.raises(WebError) as exc:
        fetch_image(f"{server}{path}", 1000, allow_private=True)
    assert exc.value.code == code


def test_fetch_image_refuses_the_local_network(server):
    with pytest.raises(WebError) as exc:
        fetch_image(f"{server}/img.png", 1000)
    assert exc.value.code == "blocked_address"
    with pytest.raises(WebError) as exc:
        fetch_image("file:///etc/passwd", 1000)
    assert exc.value.code == "invalid_url"


# --- Settings API -----------------------------------------------------------------------------

URL = "/api/system/settings/"


@pytest.fixture
def admin_client(client, db):
    user = get_user_model().objects.create_user("admin", password="x-strong-1", is_staff=True)
    client.force_login(user)
    return client


@pytest.fixture
def user_client(client, db):
    user = get_user_model().objects.create_user("user", password="x-strong-1")
    client.force_login(user)
    return client


def test_administrators_edit_the_settings(admin_client):
    assert admin_client.get(URL).json()["searxng_url"] == ""
    r = admin_client.patch(
        URL, {"searxng_url": " http://192.168.0.22:30053/ "}, content_type="application/json"
    )
    assert r.status_code == 200, r.json()
    assert r.json()["searxng_url"] == "http://192.168.0.22:30053"
    assert r.json()["photo_search_enabled"] is True
    assert SystemSettings.current().searxng_url == "http://192.168.0.22:30053"
    r = admin_client.patch(URL, {"searxng_url": "not a url"}, content_type="application/json")
    assert r.status_code == 400


def test_other_users_only_see_what_is_enabled(user_client):
    SystemSettings.objects.update_or_create(pk=1, defaults={"searxng_url": "http://searx"})
    assert user_client.get(URL).json() == {"photo_search_enabled": True}
    r = user_client.patch(URL, {"searxng_url": ""}, content_type="application/json")
    assert r.status_code == 403
    r = user_client.post(f"{URL}test-searxng/", {"searxng_url": "http://searx"})
    assert r.status_code == 403


def test_test_searxng(admin_client, server):
    r = admin_client.post(
        f"{URL}test-searxng/", {"searxng_url": server}, content_type="application/json"
    )
    assert r.json() == {"results": 2}
    r = admin_client.post(
        f"{URL}test-searxng/", {"searxng_url": f"{server}/no-json"}, content_type="application/json"
    )
    assert r.status_code == 502
    assert "settings.yml" in r.json()["detail"]
