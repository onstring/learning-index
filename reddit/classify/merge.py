#!/usr/bin/env python3
"""Validate subagent labels, join them to the scraped posts, write ranked outputs.

Usage:
    python3 classify/merge.py --data reddit_top --work classify/work --out results
Exit code 2 and a list of missing/invalid ids if labels are incomplete.
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(sys.maxsize)

CATEGORIES = {"education", "analysis", "personal_lesson", "milestone_brag",
              "news_commentary", "humour", "question", "other", "image_only"}
KEEP = {"education", "analysis", "personal_lesson"}
MIN_VALUE = 4
OUT_FIELDS = ["subreddit", "rank", "category", "learning_value", "scope",
              "topics", "takeaway", "title", "post_url", "reason", "id"]
# labels_pass2.jsonl sorts after labels_NN.jsonl, so strict pass-2 labels
# override the first pass for the shortlisted ids.


def load_posts(data_dir: Path) -> dict[str, dict]:
    posts = {}
    for path in sorted(data_dir.glob("*_top_*.csv")):
        if path.name.startswith("all_"):
            continue
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                posts.setdefault(r["id"], r)
    return posts


def valid(label: dict) -> bool:
    return (isinstance(label.get("id"), str)
            and label.get("category") in CATEGORIES
            and isinstance(label.get("learning_value"), int)
            and 1 <= label["learning_value"] <= 5
            and isinstance(label.get("topics"), list)
            and isinstance(label.get("takeaway"), str))


def load_labels(work: Path) -> tuple[dict[str, dict], list[str]]:
    labels, bad = {}, []
    files = [work / "auto_labels.jsonl", *sorted(work.glob("labels_*.jsonl"))]
    for path in files:
        if not path.exists():
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                lab = json.loads(line)
            except json.JSONDecodeError:
                bad.append(f"{path.name}:{n} not JSON")
                continue
            if not valid(lab):
                bad.append(f"{path.name}:{n} invalid {lab.get('id')}")
                continue
            labels[lab["id"]] = lab
    return labels, bad


def joined_rows(posts: dict, labels: dict) -> list[dict]:
    rows = []
    for pid, lab in labels.items():
        p = posts[pid]
        rows.append({
            "subreddit": p["subreddit"], "rank": int(p["rank"]),
            "category": lab["category"], "learning_value": lab["learning_value"],
            "scope": lab.get("scope", ""),
            "topics": "; ".join(lab["topics"]), "takeaway": lab["takeaway"],
            "title": p["title"], "post_url": p["post_url"],
            "reason": lab.get("reason", ""), "id": pid,
        })
    return sorted(rows, key=lambda r: (r["subreddit"].lower(),
                                       -r["learning_value"], r["rank"]))


def dedupe(rows: list[dict]) -> list[dict]:
    """Drop reposts: same subreddit and title, keep the higher-ranked one."""
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: r["rank"]):
        key = (r["subreddit"].lower(), r["title"].strip().lower())
        if key not in seen:
            seen.add(key)
            out.append(r)
    return sorted(out, key=lambda r: (r["subreddit"].lower(),
                                      -r["learning_value"], r["rank"]))


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        w.writeheader()
        w.writerows(rows)


def markdown_section(heading: str, rows: list[dict]) -> list[str]:
    by_sub = defaultdict(list)
    for r in rows:
        by_sub[r["subreddit"]].append(r)
    lines = [f"## {heading} ({len(rows)})", ""]
    for sub in sorted(by_sub, key=str.lower):
        lines += [f"### r/{sub} ({len(by_sub[sub])})", ""]
        for r in by_sub[sub]:
            lines.append(f"- **[{r['title']}]({r['post_url']})** "
                         f"({r['learning_value']}/5, {r['category']}, "
                         f"{r['scope'] or 'n/a'}, #{r['rank']}; "
                         f"{r['topics']})  ")
            lines.append(f"  {r['takeaway']}")
        lines.append("")
    return lines


def write_markdown(path: Path, top: list[dict], more: list[dict]) -> None:
    lines = ["# Reddit investing reading list", "",
             f"Posts labelled {', '.join(sorted(KEEP))}. Top picks score "
             f"{MIN_VALUE}+; worth a look scores {MIN_VALUE - 1}. Sorted by "
             "learning value, then Reddit top rank.", "",
             "Note: only the post itself was assessed. Comments often hold "
             "more insight; open the link to read them.", ""]
    lines += markdown_section("Top picks", top)
    lines += markdown_section("Worth a look", more)
    path.write_text("\n".join(lines), encoding="utf-8")


def load_ids(work: Path) -> set[str]:
    """Ids reviewed by the strict pass (labels_pass2.jsonl or labels_pass2_NN.jsonl)."""
    ids = set()
    for path in sorted(work.glob("labels_pass2*.jsonl")):
        ids |= {json.loads(line)["id"]
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()}
    return ids


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="reddit_top")
    ap.add_argument("--work", default="classify/work")
    ap.add_argument("--out", default="results")
    args = ap.parse_args()

    posts = load_posts(Path(args.data))
    labels, bad = load_labels(Path(args.work))
    unknown = [i for i in labels if i not in posts]
    missing = [i for i in posts if i not in labels]
    for msg in bad:
        print("BAD", msg)
    if unknown:
        print("UNKNOWN ids:", " ".join(unknown))
    if missing or bad or unknown:
        print(f"MISSING {len(missing)}:", " ".join(missing))
        sys.exit(2)

    rows = joined_rows(posts, labels)
    keep = dedupe([r for r in rows
                   if r["category"] in KEEP and r["learning_value"] >= MIN_VALUE])
    # "Worth a look": only posts that went through the strict second pass.
    reviewed = load_ids(Path(args.work))
    more = dedupe([r for r in rows
                   if r["id"] in reviewed and r["category"] in KEEP
                   and r["learning_value"] == MIN_VALUE - 1])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "all_labelled.csv", rows)
    write_csv(out / "reading_list.csv", keep)
    write_csv(out / "worth_a_look.csv", more)
    write_markdown(out / "reading_list.md", keep, more)

    counts = defaultdict(int)
    for r in rows:
        counts[r["category"]] += 1
    print("labelled:", len(rows), dict(sorted(counts.items())))
    print("reading list:", len(keep), "top +", len(more), "worth a look ->",
          out / "reading_list.md")


if __name__ == "__main__":
    main()
