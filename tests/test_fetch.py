import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from hnlearn import fetch, jsonl

PAGE = b"""<html><head><title> My  Page | Site </title>
<meta name="description" content="A &amp; B description"><script>junk()</script></head>
<body><nav>menu</nav><main><p>Hello there.</p><p>Second paragraph.</p></main></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server API
        if self.path == "/ok.html":
            self._send(200, "text/html; charset=utf-8", PAGE)
        elif self.path == "/og.html":
            self._send(200, "text/html", b'<meta property="og:description" content="OG desc">x')
        elif self.path == "/file.pdf":
            self._send(200, "application/pdf", b"%PDF-1.4 binary")
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/ok.html")
            self.end_headers()
        elif self.path == "/forbidden":
            self._send(403, "text/html", b"<title>Blocked</title>")
        else:
            self._send(404, "text/html", b"nope")

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # silence
        pass


@pytest.fixture(scope="module")
def server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_fetch_one_parses_html(server):
    r = fetch.fetch_one(server + "/ok.html")
    assert r["status"] == 200 and r["error"] is None
    assert r["title"] == "My Page | Site"
    assert r["description"] == "A & B description"
    assert r["snippet"] == "Hello there. Second paragraph."
    assert r["final_url"] == server + "/ok.html"
    assert r["content_type"].startswith("text/html")


def test_fetch_one_og_description_and_redirect(server):
    assert fetch.fetch_one(server + "/og.html")["description"] == "OG desc"
    r = fetch.fetch_one(server + "/redirect")
    assert r["status"] == 200 and r["final_url"].endswith("/ok.html")


def test_fetch_one_non_html_has_no_text(server):
    r = fetch.fetch_one(server + "/file.pdf")
    assert r["status"] == 200 and r["title"] is None and r["snippet"] is None
    assert r["content_type"] == "application/pdf"


def test_fetch_one_http_errors(server):
    r = fetch.fetch_one(server + "/forbidden")
    assert r["status"] == 403 and r["error"] is None and r["title"] == "Blocked"
    assert fetch.fetch_one(server + "/missing")["status"] == 404


def test_fetch_one_connection_failure():
    r = fetch.fetch_one("http://127.0.0.1:9/x", timeout=1)
    assert r["status"] is None and r["error"]


def test_scheme_urls():
    assert fetch.scheme_urls("a.com/x") == ["https://a.com/x", "http://a.com/x"]


def test_run_is_resumable_and_respects_limit(server, tmp_path, monkeypatch):
    cands = tmp_path / "candidates.jsonl"
    for nurl in ("one", "two", "three"):
        jsonl.append(cands, {"nurl": nurl})
    monkeypatch.setattr(fetch, "scheme_urls", lambda nurl: [f"{server}/ok.html"])
    out = tmp_path / "fetch.jsonl"
    assert fetch.run(cands, out, limit=2, workers=2) == 2
    assert fetch.run(cands, out, workers=2) == 1
    rows = list(jsonl.read(out))
    assert [r["nurl"] for r in rows] == ["one", "two", "three"]
    assert all(r["status"] == 200 and "fetched_at" in r for r in rows)
    assert fetch.run(cands, out) == 0


def test_run_falls_back_to_second_scheme(server, tmp_path, monkeypatch):
    cands = tmp_path / "c.jsonl"
    jsonl.append(cands, {"nurl": "x"})
    monkeypatch.setattr(fetch, "scheme_urls",
                        lambda nurl: ["http://127.0.0.1:9/dead", f"{server}/ok.html"])
    out = tmp_path / "f.jsonl"
    fetch.run(cands, out, timeout=1)
    row = json.loads(out.read_text().splitlines()[0])
    assert row["status"] == 200 and row["url"] == f"{server}/ok.html"
