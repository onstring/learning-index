"""Stage 3: fetch each candidate page once; record status, title, description, text snippet."""

from __future__ import annotations

import html
import logging
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hnlearn import config, jsonl, text

log = logging.getLogger(__name__)

_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_META = re.compile(r"<meta\s+[^>]*>", re.I | re.S)
_ATTR = re.compile(r"""([\w:-]+)\s*=\s*("([^"]*)"|'([^']*)')""", re.S)
_DESC_KEYS = ("description", "og:description", "twitter:description")


def scheme_urls(nurl: str) -> list[str]:
    """URLs to try for a normalised URL: https first, then http for old sites."""
    return [f"https://{nurl}", f"http://{nurl}"]


def fetch_one(url: str, *, timeout: float = config.FETCH_TIMEOUT_S,
              max_bytes: int = config.FETCH_MAX_BYTES) -> dict[str, Any]:
    """GET one URL. Never raises; failures are recorded in ``error``."""
    out: dict[str, Any] = {"url": url, "status": None, "error": None, "final_url": None,
                           "content_type": None, "title": None, "description": None,
                           "snippet": None}
    req = urllib.request.Request(url, headers={"User-Agent": config.FETCH_USER_AGENT,
                                               "Accept": "text/html,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read(max_bytes)
            return {**out, **_describe(resp.status, resp.geturl(), resp.headers, body)}
    except urllib.error.HTTPError as e:
        body = e.read(max_bytes) if e.fp else b""
        return {**out, **_describe(e.code, e.geturl(), e.headers, body)}
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError, OSError) as e:
        reason = getattr(e, "reason", e)
        return {**out, "error": f"{type(e).__name__}: {str(reason)[:120]}"}


def _describe(status: int, final_url: str, headers: Any, body: bytes) -> dict[str, Any]:
    ctype = headers.get("Content-Type", "") if headers else ""
    out: dict[str, Any] = {"status": status, "final_url": final_url, "content_type": ctype}
    if ctype and "html" not in ctype and "xml" not in ctype and "text" not in ctype:
        return out
    charset = headers.get_content_charset() if headers else None
    markup = body.decode(charset or "utf-8", "replace")
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


def fetch_candidate(nurl: str, *, timeout: float = config.FETCH_TIMEOUT_S) -> dict[str, Any]:
    """Try each scheme in turn; return the first HTTP answer, else the last failure."""
    result: dict[str, Any] = {}
    for url in scheme_urls(nurl):
        result = fetch_one(url, timeout=timeout)
        if result["status"] is not None:
            break
    return {"nurl": nurl, "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"), **result}


def run(candidates_path: Path, out_path: Path, *, limit: int | None = None,
        workers: int = config.FETCH_WORKERS, timeout: float = config.FETCH_TIMEOUT_S) -> int:
    """Fetch every candidate not already in ``out_path``. Returns rows written."""
    done = jsonl.done_keys(out_path, "nurl")
    todo = [c["nurl"] for c in jsonl.read(candidates_path) if c["nurl"] not in done]
    if limit is not None:
        todo = todo[:limit]
    log.info("fetch: %d to do, %d already done", len(todo), len(done))
    written = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(lambda n: fetch_candidate(n, timeout=timeout), todo):
            jsonl.append(out_path, row)
            written += 1
            if written % 100 == 0:
                log.info("fetch: %d/%d", written, len(todo))
    return written
