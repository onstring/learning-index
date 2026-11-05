"""Fetch page <title> and meta description for each eval item.

Usage: python -I eval_fetch.py <in.jsonl> <out.jsonl>
"""
import html
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

IN, OUT = sys.argv[1], sys.argv[2]
UA = "Mozilla/5.0 (compatible; hn-learn-eval/0.1)"


def fetch(item):
    url = "https://" + item["nurl"]
    out = {**item, "http_status": None, "page_title": None, "page_desc": None}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=12) as resp:
            out["http_status"] = resp.status
            body = resp.read(200_000).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 - record and move on
        out["http_status"] = getattr(e, "code", None) or str(e)[:80]
        return out
    m = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
    if m:
        out["page_title"] = html.unescape(re.sub(r"\s+", " ", m.group(1))).strip()[:200]
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', body, re.I)
    if m:
        out["page_desc"] = html.unescape(m.group(1)).strip()[:300]
    return out


items = [json.loads(line) for line in open(IN)]
with ThreadPoolExecutor(max_workers=12) as ex:
    results = list(ex.map(fetch, items))
with open(OUT, "w") as f:
    for r in results:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
ok = sum(1 for r in results if r["http_status"] == 200)
print(f"fetched {len(results)}, http 200: {ok}, with title: {sum(1 for r in results if r['page_title'])}")
