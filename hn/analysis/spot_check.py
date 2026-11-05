"""Print a reproducible random sample of kept resources for a manual rubric check.

Usage: uv run python -I analysis/spot_check.py data/resources.json [n] [seed]
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter

path = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 30
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
doc = json.load(open(path, encoding="utf-8"))
res = doc["resources"]
print(f"resources={len(res)} generated={doc['generated_at']}")
print("topics:", ", ".join(f"{t['key']}={t['count']}" for t in doc["topics"]))
print("types:", dict(Counter(r["resource_type"] for r in res)))
print("difficulty:", dict(Counter(r["difficulty_label"] for r in res)))
print("unverified:", sum(r["unverified"] for r in res), "missing blurb:",
      sum(1 for r in res if not r["blurb"]))
rng = random.Random(seed)
for r in rng.sample(res, min(n, len(res))):
    print(f"\n#{r['rank']} [{r['topic']}/{r['resource_type']}/{r['difficulty_label']}] "
          f"p={r['keep_prob']:.2f} ppl={r['ppl']} {r['title'][:80]}")
    print(f"   {r['url'][:100]}")
    print(f"   {r['blurb'][:200]}")
