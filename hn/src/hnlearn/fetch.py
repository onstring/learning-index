"""Stage 3: fetch each candidate page once; record status, title, description, text snippet.

Targets come from untrusted data, so every URL (and every redirect) must be http(s) to a
public address. Transient failures (no answer, 5xx) are retried on the next run.
"""

from __future__ import annotations

import codecs
import html
import http.client
import ipaddress
import logging
import re
import socket
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from hnlearn import config, jsonl, text

log = logging.getLogger(__name__)

_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_META = re.compile(r"<meta\s+[^>]*>", re.I | re.S)
_ATTR = re.compile(r"""([\w:-]+)\s*=\s*("([^"]*)"|'([^']*)')""", re.S)
_DESC_KEYS = ("description", "og:description", "twitter:description")
_LOCAL_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa")
_PATH_SAFE = "/%:@&=+$,;~!*'()[]"
_QUERY_SAFE = "=&%+/:,;?@!$'()*[]~"


class BlockedURL(ValueError):
    """The URL is not an http(s) URL to a public host."""


def scheme_urls(nurl: str) -> list[str]:
    """URLs to try for a normalised URL: https first, then http for old sites."""
    return [f"https://{nurl}", f"http://{nurl}"]


def encode_url(url: str) -> str:
    """IDNA-encode the host and percent-encode path and query so urllib accepts the URL."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as e:
        raise BlockedURL(f"bad host {host!r}") from e
    netloc = host + (f":{parts.port}" if parts.port else "")
    return urlunsplit((parts.scheme, netloc, quote(parts.path, safe=_PATH_SAFE),
                       quote(parts.query, safe=_QUERY_SAFE), ""))


def is_private_host(host: str) -> bool:
    """True when the host is loopback, private, link-local or otherwise not public."""
    h = host.strip("[]").lower()
    if h == "localhost" or h.endswith(_LOCAL_SUFFIXES):
        return True
    try:
        infos = socket.getaddrinfo(h, None)
    except socket.gaierror:
        return False  # unknown host: let the fetch fail on its own
    for _family, _type, _proto, _name, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if not ip.is_global or ip.is_multicast:
            return True
    return False


def check_target(url: str, allow_private: bool = False) -> None:
    """Raise BlockedURL unless ``url`` is http(s) to a public host with no credentials."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise BlockedURL(f"scheme {parts.scheme!r} not allowed")
    if not parts.hostname:
        raise BlockedURL("no host")
    if parts.username or parts.password:
        raise BlockedURL("credentials in URL")
    if not allow_private and is_private_host(parts.hostname):
        raise BlockedURL(f"private address {parts.hostname}")


class _Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, allow_private: bool) -> None:
        super().__init__()
        self.allow_private = allow_private

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        check_target(newurl, self.allow_private)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENERS: dict[bool, urllib.request.OpenerDirector] = {}


def _opener(allow_private: bool) -> urllib.request.OpenerDirector:
    if allow_private not in _OPENERS:
        _OPENERS[allow_private] = urllib.request.build_opener(_Redirects(allow_private))
    return _OPENERS[allow_private]


def fetch_one(url: str, *, timeout: float = config.FETCH_TIMEOUT_S,
              max_bytes: int = config.FETCH_MAX_BYTES,
              allow_private: bool = False) -> dict[str, Any]:
    """GET one URL. Never raises; failures are recorded in ``error``."""
    out: dict[str, Any] = {"url": url, "status": None, "error": None, "final_url": None,
                           "content_type": None, "title": None, "description": None,
                           "snippet": None}
    try:
        url = encode_url(url)
        check_target(url, allow_private)
        req = urllib.request.Request(url, headers={"User-Agent": config.FETCH_USER_AGENT,
                                                   "Accept": "text/html,*/*;q=0.8"})
        with _opener(allow_private).open(req, timeout=timeout) as resp:
            body = resp.read(max_bytes)
            return {**out, "url": url, **_describe(resp.status, resp.geturl(), resp.headers, body)}
    except urllib.error.HTTPError as e:
        try:
            body = e.read(max_bytes) if e.fp else b""
        except (http.client.HTTPException, OSError):
            body = b""
        finally:
            e.close()
        return {**out, "url": url, **_describe(e.code, e.geturl(), e.headers, body)}
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ValueError,
            LookupError, OSError) as e:
        reason = getattr(e, "reason", e)
        return {**out, "error": f"{type(e).__name__}: {str(reason)[:120]}"}


def _describe(status: int, final_url: str, headers: Any, body: bytes) -> dict[str, Any]:
    ctype = headers.get("Content-Type", "") if headers else ""
    out: dict[str, Any] = {"status": status, "final_url": final_url, "content_type": ctype}
    if ctype and "html" not in ctype and "xml" not in ctype and "text" not in ctype:
        return out
    charset = (headers.get_content_charset() if headers else None) or "utf-8"
    try:
        codecs.lookup(charset)
    except LookupError:
        charset = "utf-8"
    markup = body.decode(charset, "replace")
    return {**out, "title": _title(markup), "description": _description(markup),
            "snippet": text.truncate(text.html_to_text(markup), config.SNIPPET_CHARS) or None}


def _title(markup: str) -> str | None:
    m = _TITLE.search(markup)
    if not m:
        return None
    t = re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()
    return t[:200] or None


def _description(markup: str) -> str | None:
    found: dict[str, str] = {}
    for tag in _META.findall(markup):
        attrs = {k.lower(): (v2 if v2 is not None else v3)
                 for k, _, v2, v3 in _ATTR.findall(tag)}
        key = (attrs.get("name") or attrs.get("property") or "").lower()
        if key in _DESC_KEYS and attrs.get("content"):
            found[key] = html.unescape(attrs["content"]).strip()[:300]
    for key in _DESC_KEYS:
        if found.get(key):
            return found[key]
    return None


def fetch_candidate(nurl: str, *, timeout: float = config.FETCH_TIMEOUT_S,
                    allow_private: bool = False) -> dict[str, Any]:
    """Try each scheme in turn; return the first HTTP answer, else the last failure."""
    result: dict[str, Any] = {}
    for url in scheme_urls(nurl):
        result = fetch_one(url, timeout=timeout, allow_private=allow_private)
        if result["status"] is not None or (result["error"] or "").startswith("BlockedURL"):
            break
    return {"nurl": nurl, "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"), **result}


def is_final(row: dict[str, Any]) -> bool:
    """A row that need not be fetched again: any HTTP answer below 500, or a blocked URL."""
    status = row.get("status")
    if status is not None:
        return status < 500
    return (row.get("error") or "").startswith("BlockedURL")


def run(candidates_path: Path, out_path: Path, *, limit: int | None = None,
        workers: int = config.FETCH_WORKERS, timeout: float = config.FETCH_TIMEOUT_S,
        allow_private: bool = False) -> int:
    """Fetch every candidate without a final row in ``out_path``. Returns rows written.

    Later rows for the same URL supersede earlier ones; readers keep the last.
    """
    previous = {r["nurl"]: r for r in jsonl.read(out_path)}
    done = {n for n, r in previous.items() if is_final(r)}
    todo = [c["nurl"] for c in jsonl.read(candidates_path) if c["nurl"] not in done]
    if limit is not None:
        todo = todo[:limit]
    log.info("fetch: %d to do, %d already done", len(todo), len(done))
    written = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch_candidate, n, timeout=timeout, allow_private=allow_private)
                   for n in todo]
        try:
            for fut in as_completed(futures):
                jsonl.append(out_path, fut.result())
                written += 1
                if written % 100 == 0:
                    log.info("fetch: %d/%d", written, len(todo))
        except BaseException:
            pool.shutdown(cancel_futures=True)
            raise
    return written
