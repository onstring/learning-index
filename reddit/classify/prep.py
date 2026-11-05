#!/usr/bin/env python3
"""Bucket scraped posts and split the ones worth classifying into JSONL chunks.

Buckets:
  image_only  image/video post with a short caption -> auto-labelled, not sent to LLM
  link        external link post (judged from title + domain)
  text/image  everything else, body truncated

Usage:
    python3 classify/prep.py --data reddit_top --out classify/work --chunk 100
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

csv.field_size_limit(sys.maxsize)

IMAGE_ONLY_MAX_BODY = 200   # chars; shorter image captions are auto-skipped
BODY_TRUNCATE = 1500        # chars sent to the classifier


def load_rows(data_dir: Path, subs: set[str] | None = None) -> list[dict]:
    rows = []
    for path in sorted(data_dir.glob("*_top_*.csv")):
        if path.name.startswith("all_"):  # combined file, duplicates the rest
            continue
        if subs and path.name.split("_top_")[0].lower() not in subs:
            continue
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if "body" not in (reader.fieldnames or []):
                sys.exit(f"{path} has no body column; re-run reddit_top.py")
            rows.extend(reader)
    return rows


def kind_of(row: dict) -> str:
    if row["is_image"] == "1":
        return "image"
    content, post = row["content_url"], row["post_url"]
    if content and content.rstrip("/") != post.rstrip("/"):
        return "link"
    return "text"


def to_item(row: dict) -> dict:
    body = row["body"]
    if len(body) > BODY_TRUNCATE:
        body = body[:BODY_TRUNCATE] + " …[truncated]"
    return {
        "id": row["id"],
        "subreddit": row["subreddit"],
        "rank": int(row["rank"]),
        "title": row["title"],
        "kind": kind_of(row),
        "domain": urlparse(row["content_url"]).netloc,
        "body": body,
    }


def auto_label(item: dict) -> dict:
    return {
        "id": item["id"],
        "category": "image_only",
        "learning_value": 1,
        "topics": [],
        "takeaway": "",
        "reason": "Image post with short caption; not sent to classifier.",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="reddit_top")
    ap.add_argument("--out", default="classify/work")
    ap.add_argument("--chunk", type=int, default=100)
    ap.add_argument("--subs", nargs="+",
                    help="only these subreddits (e.g. to add one new sub)")
    args = ap.parse_args()

    subs = {s.lower() for s in args.subs} if args.subs else None
    rows = load_rows(Path(args.data), subs)
    if not rows:
        sys.exit("no posts found; check --data and --subs")
    seen, items = set(), []
    for r in rows:  # same post can appear in two subs' top lists only by id clash
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        items.append(to_item(r))

    auto = [i for i in items
            if i["kind"] == "image" and len(i["body"]) < IMAGE_ONLY_MAX_BODY]
    auto_ids = {i["id"] for i in auto}
    todo = [i for i in items if i["id"] not in auto_ids]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("chunk_*.jsonl"):
        old.unlink()
    with open(out / "auto_labels.jsonl", "w", encoding="utf-8") as f:
        for i in auto:
            f.write(json.dumps(auto_label(i), ensure_ascii=False) + "\n")
    for n, start in enumerate(range(0, len(todo), args.chunk)):
        with open(out / f"chunk_{n:02d}.jsonl", "w", encoding="utf-8") as f:
            for i in todo[start:start + args.chunk]:
                f.write(json.dumps(i, ensure_ascii=False) + "\n")

    kinds = {}
    for i in todo:
        kinds[i["kind"]] = kinds.get(i["kind"], 0) + 1
    print(f"posts: {len(items)}  auto image_only: {len(auto)}  "
          f"to classify: {len(todo)} {kinds}  "
          f"chunks: {(len(todo) + args.chunk - 1) // args.chunk}")


if __name__ == "__main__":
    main()
