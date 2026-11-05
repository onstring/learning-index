#!/usr/bin/env python3
"""Download the top posts (all time) for a list of subreddits via Reddit RSS.

Standard library only. Python 3.9+.
Note: Reddit has announced RSS support ends on 13 November 2026.

Usage:
    python3 reddit_top.py                      # top 200, all time, ./reddit_top/
    python3 reddit_top.py --limit 100 --time year --out ./data
    python3 reddit_top.py --subs ETFs stocks
"""
import argparse
import csv
import html
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

SUBREDDITS = [
    "investing", "Bogleheads", "ETFs", "dividends", "ValueInvesting",
    "AusFinance", "fiaustralia", "financialindependence", "stocks", "LETFs",
]
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
NS = {"a": "http://www.w3.org/2005/Atom"}
PAGE_SIZE = 100  # Reddit's per-request maximum
LINK_RE = re.compile(r'<a href="([^"]+)">\[link\]</a>')
BODY_RE = re.compile(r"<!-- SC_OFF -->(.*?)<!-- SC_ON -->", re.S)
MEDIA_RE = re.compile(
    r"^https?://(i\.redd\.it|v\.redd\.it|i\.imgur\.com|imgur\.com"
    r"|preview\.redd\.it|www\.reddit\.com/gallery)/", re.I)
FIELDS = ["subreddit", "rank", "id", "title", "author", "published",
          "post_url", "content_url", "is_image", "body"]
BLOCK_TAGS = {"p", "br", "li", "div", "pre", "blockquote", "tr",
              "h1", "h2", "h3", "h4", "h5", "h6"}


class _TextExtractor(HTMLParser):
    """Turn Reddit's selftext HTML into plain text, keeping paragraph breaks."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self.parts.append("\n- ")
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(fragment):
    p = _TextExtractor()
    p.feed(fragment)
    p.close()
    text = "".join(p.parts)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\s*\n\s*(\n\s*)+", "\n\n", text).strip()


def extract_body(content):
    m = BODY_RE.search(content)
    return html_to_text(m.group(1)) if m else ""


_next_ok = 0.0  # monotonic time before which we must not send a request


def _wait_turn():
    wait = _next_ok - time.monotonic()
    if wait > 0:
        print(f"  waiting {wait:.0f}s for rate limit reset", file=sys.stderr)
        time.sleep(wait)


def _update_limit(headers):
    """Respect x-ratelimit-remaining / x-ratelimit-reset (seconds)."""
    global _next_ok
    try:
        remaining = float(headers.get("x-ratelimit-remaining", 1))
        reset = float(headers.get("x-ratelimit-reset", 0))
    except ValueError:
        return
    if remaining < 1 and reset > 0:
        _next_ok = time.monotonic() + reset + 2


def fetch(url, retries=5):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(1, retries + 1):
        _wait_turn()
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                _update_limit(r.headers)
                return r.read()
        except urllib.error.HTTPError as e:
            _update_limit(e.headers)
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                ra = int(e.headers.get("retry-after") or 0)
                wait = max(ra, 5 * 2 ** attempt, _next_ok - time.monotonic())
                print(f"  HTTP {e.code}, retrying in {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as e:
            if attempt < retries:
                wait = 5 * 2 ** attempt
                print(f"  {e.reason}, retrying in {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise


def parse(xml_bytes, sub):
    root = ET.fromstring(xml_bytes)
    rows = []
    for e in root.findall("a:entry", NS):
        content = e.findtext("a:content", "", NS)
        m = LINK_RE.search(content)
        content_url = html.unescape(m.group(1)) if m else ""
        link = e.find("a:link", NS)
        rows.append({
            "subreddit": sub,
            "id": e.findtext("a:id", "", NS),
            "title": e.findtext("a:title", "", NS),
            "author": e.findtext("a:author/a:name", "", NS).removeprefix("/u/"),
            "published": (e.findtext("a:published", "", NS)
                          or e.findtext("a:updated", "", NS)),
            "post_url": link.get("href") if link is not None else "",
            "content_url": content_url,
            "is_image": int(bool(MEDIA_RE.match(content_url))),
            "body": extract_body(content),
        })
    return rows


def fetch_sub(sub, total, t, delay):
    rows, seen, after = [], set(), None
    while len(rows) < total:
        params = {"t": t, "limit": min(PAGE_SIZE, total - len(rows))}
        if after:
            params["after"] = after
            params["count"] = len(rows)
        url = (f"https://www.reddit.com/r/{sub}/top/.rss?"
               f"{urllib.parse.urlencode(params)}")
        page = parse(fetch(url), sub)
        new = [r for r in page if r["id"] not in seen]
        if not new:
            break
        for r in new:
            seen.add(r["id"])
            r["rank"] = len(rows) + 1
            rows.append(r)
        if len(page) < params["limit"]:
            break  # no more posts
        after = page[-1]["id"]
        time.sleep(delay)
    return rows


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subs", nargs="+", default=SUBREDDITS)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--time", default="all",
                    choices=["hour", "day", "week", "month", "year", "all"])
    ap.add_argument("--out", default="reddit_top")
    ap.add_argument("--delay", type=float, default=2.0,
                    help="minimum seconds between requests (default 2); "
                         "rate-limit headers add more wait as needed")
    ap.add_argument("--force", action="store_true",
                    help="re-download subreddits that already have a CSV")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    combined = []

    for i, sub in enumerate(args.subs):
        path = out / f"{sub}_top_{args.time}.csv"
        if path.exists() and not args.force:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                has_all_fields = set(FIELDS) <= set(reader.fieldnames or [])
            if has_all_fields:
                combined.extend(rows)
                print(f"r/{sub} ... skipped, {len(rows)} posts already in "
                      f"{path.name}")
                continue
            print(f"r/{sub} ... old CSV lacks body column, re-fetching")
        print(f"r/{sub} ...", end=" ", flush=True)
        try:
            rows = fetch_sub(sub, args.limit, args.time, args.delay)
        except Exception as e:  # keep going with the other subreddits
            print(f"FAILED: {e}")
            continue
        write_csv(out / f"{sub}_top_{args.time}.csv", rows)
        combined.extend(rows)
        note = "" if len(rows) >= args.limit else f" (fewer than {args.limit})"
        print(f"{len(rows)} posts{note}")
        if i < len(args.subs) - 1:
            time.sleep(args.delay)

    write_csv(out / f"all_top_{args.time}.csv", combined)
    print(f"Wrote {len(combined)} rows to {out}/")


if __name__ == "__main__":
    main()
