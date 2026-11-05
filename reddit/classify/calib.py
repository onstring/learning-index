#!/usr/bin/env python3
"""Compare hand labels (calib_mine.jsonl) with subagent labels (labels_*.jsonl).

Reports category agreement and keep/drop agreement (the decision that matters).
"""
import glob
import json
from pathlib import Path

WORK = Path(__file__).parent / "work"
KEEP = {"education", "analysis", "personal_lesson"}
MIN_VALUE = 4


def kept(lab: dict) -> bool:
    return lab["category"] in KEEP and lab["learning_value"] >= MIN_VALUE


def main() -> None:
    mine = {d["id"]: d for d in map(json.loads, open(WORK / "calib_mine.jsonl"))}
    theirs = {}
    for f in sorted(glob.glob(str(WORK / "labels_*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            if line.strip():
                d = json.loads(line)
                theirs[d["id"]] = d
    cat_ok = keep_ok = n = 0
    for pid, m in mine.items():
        t = theirs.get(pid)
        if t is None:
            print(f"{pid}: no subagent label")
            continue
        n += 1
        same_cat = m["category"] == t["category"]
        same_keep = kept(m) == kept(t)
        cat_ok += same_cat
        keep_ok += same_keep
        if not (same_cat and abs(m["learning_value"] - t["learning_value"]) <= 1):
            print(f"{pid}: mine {m['category']}/{m['learning_value']} "
                  f"vs {t['category']}/{t['learning_value']}  "
                  f"{'KEEP-DIFF ' if not same_keep else ''}| {t.get('reason', '')}")
    if n:
        print(f"\ncompared {n}: category agree {cat_ok}/{n} "
              f"({cat_ok / n:.0%}), keep/drop agree {keep_ok}/{n} "
              f"({keep_ok / n:.0%})")


if __name__ == "__main__":
    main()
