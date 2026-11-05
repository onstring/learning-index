#!/usr/bin/env python3
"""Render the Reddit reading lists as one static page in the shared site theme.

Writes OUT/index.html, OUT/style.css (the shared theme, copied from the HN site so both
sections look the same) and OUT/reddit.css (the few Reddit-only rules).

    python3 reddit/classify/render.py --out site/reddit \
        --set "All time" reddit/results/reading_list.csv reddit/results/worth_a_look.csv \
        --set "Past year" reddit/results_year/reading_list.csv reddit/results_year/worth_a_look.csv

The first --set is shown by default.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TEMPLATE = HERE / "index_template.html"
EXTRA_CSS = HERE / "reddit.css"
THEME_CSS = REPO / "hn" / "src" / "hnlearn" / "static" / "style.css"
TITLE = "Reddit Investing Reading List"


def slugify(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def load(path: Path, tier: str, period: str) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [{
        "id": r["id"], "period": period, "tier": tier, "sub": r["subreddit"],
        "rank": int(r["rank"]), "score": int(r["learning_value"]),
        "cat": r["category"], "scope": r.get("scope") or "n/a",
        "topics": [t.strip() for t in r["topics"].split(";") if t.strip()],
        "takeaway": r["takeaway"], "title": r["title"], "url": r["post_url"],
    } for r in rows]


def collect(sets: list[list[str]]) -> tuple[list[dict], list[dict]]:
    """Return (periods, posts). Each period: {key, label, top, more}."""
    periods, posts = [], []
    for label, top_csv, more_csv in sets:
        top = load(Path(top_csv), "top", slugify(label))
        more = load(Path(more_csv), "more", slugify(label))
        if not top and not more:
            raise SystemExit(f"no posts found for {label!r}: {top_csv}, {more_csv}")
        periods.append({"key": slugify(label), "label": label,
                        "top": len(top), "more": len(more)})
        posts += top + more
    return periods, posts


def asset_hash(*paths: Path) -> str:
    digest = hashlib.sha1()  # noqa: S324 - cache-busting only
    for p in paths:
        digest.update(p.read_bytes())
    return digest.hexdigest()[:12]


def page(periods: list[dict], posts: list[dict], build: str, today: date) -> str:
    payload = {"periods": periods, "posts": posts}
    # Escape "</" so post text can never close the <script> block.
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    summary = "; ".join(f"{p['label']}: {p['top']} top picks and {p['more']} worth a look"
                        for p in periods)
    return (TEMPLATE.read_text(encoding="utf-8")
            .replace("__DATA__", data)
            .replace("__SUMMARY__", summary)
            .replace("__TITLE__", TITLE)
            .replace("__BUILD__", build)
            .replace("__DATE__", f"{today.day} {today:%B %Y}"))


def render(sets: list[list[str]], out: Path, theme: Path = THEME_CSS,
           today: date | None = None) -> dict[str, int]:
    periods, posts = collect(sets)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(theme, out / "style.css")
    shutil.copyfile(EXTRA_CSS, out / "reddit.css")
    html = page(periods, posts, asset_hash(theme, EXTRA_CSS), today or date.today())
    (out / "index.html").write_text(html, encoding="utf-8")
    # Small summary for the hub page, so it never has to parse this HTML.
    (out / "meta.json").write_text(json.dumps({"periods": periods}, indent=1) + "\n",
                                   encoding="utf-8")
    return {"periods": len(periods), "posts": len(posts)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", nargs=3, action="append", required=True,
                    metavar=("LABEL", "TOP_CSV", "MORE_CSV"),
                    help="a period to show; repeat for several")
    ap.add_argument("--out", type=Path, default=Path("site/reddit"),
                    help="output directory (default: site/reddit)")
    ap.add_argument("--theme", type=Path, default=THEME_CSS,
                    help="shared theme stylesheet to copy in")
    args = ap.parse_args()
    stats = render(args.set, args.out, args.theme)
    print(f"wrote {stats['posts']} posts in {stats['periods']} periods -> {args.out}/")


if __name__ == "__main__":
    main()
