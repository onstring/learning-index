#!/usr/bin/env python3
"""Build the hub page (site/index.html) that links the HN and Reddit sections.

Counts come from the built sections (hn/search.json, reddit/meta.json), so the hub
rebuilds on a fresh clone without the HN dataset or the raw Reddit scrapes.

    python3 hub/build.py --site site
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TEMPLATE = HERE / "index_template.html"
THEME_CSS = REPO / "hn" / "src" / "hnlearn" / "static" / "style.css"


def read_json(path: Path) -> object:
    if not path.exists():
        raise SystemExit(f"{path} not found; build that section first")
    return json.loads(path.read_text(encoding="utf-8"))


def reddit_summary(periods: list[dict]) -> str:
    parts = []
    for i, p in enumerate(periods):
        n = p["top"] + p["more"]
        label = p["label"].lower()
        parts.append(f"{n} posts from {label}" if i == 0 else f"{n} from the {label}")
    return ", ".join(parts)


def build(site: Path, today: date | None = None) -> None:
    hn_count = len(read_json(site / "hn" / "search.json"))
    periods = read_json(site / "reddit" / "meta.json")["periods"]
    today = today or date.today()
    html = (TEMPLATE.read_text(encoding="utf-8")
            .replace("__HN_COUNT__", f"{hn_count:,}")
            .replace("__REDDIT_SUMMARY__", reddit_summary(periods))
            .replace("__DATE__", f"{today.day} {today:%B %Y}"))
    (site / "index.html").write_text(html, encoding="utf-8")
    shutil.copyfile(THEME_CSS, site / "style.css")
    (site / ".nojekyll").touch()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", type=Path, default=Path("site"))
    args = ap.parse_args()
    build(args.site)
    print(f"wrote {args.site / 'index.html'}")


if __name__ == "__main__":
    main()
