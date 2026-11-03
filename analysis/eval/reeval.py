"""Re-score the 100 evaluation URLs with the production fetch and classify stages.

Usage: uv run python -I analysis/eval/reeval.py <eval_items_fetched.jsonl> <workdir>
Writes <workdir>/eval_clef_prod.jsonl in the format eval_score.py expects.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from hnlearn import classify, fetch, jsonl

items_path, workdir = Path(sys.argv[1]), Path(sys.argv[2])
workdir.mkdir(parents=True, exist_ok=True)
cands = workdir / "candidates.jsonl"
fetched = workdir / "fetch.jsonl"
clef = workdir / "clef.jsonl"

if cands.exists():
    cands.unlink()
ids: dict[str, int] = {}
for it in jsonl.read(items_path):
    ids[it["nurl"]] = it["id"]
    jsonl.append(cands, {"nurl": it["nurl"], "host": it["host"], "ppl": it["ppl"],
                         "yrs": it["yrs"], "y0": it["y0"], "y1": it["y1"],
                         "story_title": it["story_title"], "story_score": it["best_score"],
                         "evidence": [{"author": f"a{i}", "excerpt": ex}
                                      for i, ex in enumerate(it["excerpts"] or [])]})
print("fetched", fetch.run(cands, fetched), flush=True)
rows = list(jsonl.read(fetched))
print("http 200:", sum(1 for r in rows if r["status"] == 200),
      "with snippet:", sum(1 for r in rows if r.get("snippet")),
      "with description:", sum(1 for r in rows if r.get("description")), flush=True)
print("classified", classify.run(cands, fetched, clef), flush=True)
out = workdir / "eval_clef_prod.jsonl"
with out.open("w", encoding="utf-8") as f:
    for r in jsonl.read(clef):
        f.write(json.dumps({"id": ids[r["nurl"]], "ok": True, **r}) + "\n")
print("wrote", out)
