"""Score model outputs against gold labels.

Usage: python -I eval_score.py <items.jsonl> <gold.csv> <clef.jsonl> [<qwen.jsonl>]
"""
import csv
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_rubric import BOOLS, COMPOSITE, keep_from_bools  # noqa: E402

ITEMS, GOLD = sys.argv[1], sys.argv[2]
RUNS = sys.argv[3:]
items = {json.loads(l)["id"]: json.loads(l) for l in open(ITEMS)}
gold = {int(r["id"]): {"keep": r["keep"] == "1", "border": r["borderline"] == "1",
                       "topics": set(r["topics"].split("|"))} for r in csv.DictReader(open(GOLD))}
BOOL_NAMES = [b[0] for b in BOOLS]


def load(path):
    return {json.loads(l)["id"]: json.loads(l) for l in open(path)}


def prf(pred: dict, subset):
    tp = sum(1 for i in subset if pred[i] and gold[i]["keep"])
    fp = sum(1 for i in subset if pred[i] and not gold[i]["keep"])
    fn = sum(1 for i in subset if not pred[i] and gold[i]["keep"])
    acc = sum(1 for i in subset if pred[i] == gold[i]["keep"]) / len(subset)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return acc, p, r


def report_keep(name, pred):
    ids = [i for i in pred if i in gold]
    conf = [i for i in ids if not gold[i]["border"]]
    a, p, r = prf(pred, ids)
    ac, pc, rc = prf(pred, conf)
    strata = {}
    for i in ids:
        s = items[i]["stratum"]
        strata.setdefault(s, []).append(pred[i] == gold[i]["keep"])
    per = " ".join(f"{s}={sum(v)/len(v):.2f}" for s, v in sorted(strata.items()))
    print(f"  {name:<28} all n={len(ids)}: acc={a:.2f} P={p:.2f} R={r:.2f} | "
          f"confident n={len(conf)}: acc={ac:.2f} P={pc:.2f} R={rc:.2f} | {per}")


def topic_acc(run, label):
    ok = [i for i, r in run.items() if r.get("ok") and gold[i]["keep"]]
    hit = sum(1 for i in ok if run[i].get("topic") in gold[i]["topics"])
    print(f"  {label:<28} topic acc on gold-keep n={len(ok)}: {hit/len(ok):.2f}")


def summarise(path):
    run = load(path)
    okr = {i: r for i, r in run.items() if r.get("ok")}
    lat = [r["latency"] for r in okr.values()]
    fails = len(run) - len(okr)
    print(f"\n== {os.path.basename(path)}: n={len(run)} failures={fails} "
          f"latency mean={statistics.mean(lat):.2f}s median={statistics.median(lat):.2f}s "
          f"max={max(lat):.2f}s")
    preds = {}
    if "is_free_learning_resource" in next(iter(okr.values())):  # clef
        for t in (0.3, 0.5, 0.7):
            preds[f"clef rule@{t}"] = {i: keep_from_bools({b: r[b] > t for b in BOOL_NAMES})
                                       for i, r in okr.items()}
            preds[f"clef composite@{t}"] = {i: r[COMPOSITE[0]] > t for i, r in okr.items()}
    else:  # qwen
        preds["qwen rule"] = {i: keep_from_bools({b: bool(r[b]) for b in BOOL_NAMES})
                              for i, r in okr.items()}
        preds["qwen own keep"] = {i: bool(r["keep"]) for i, r in okr.items()}
    for name, p in preds.items():
        report_keep(name, p)
    topic_acc(okr, os.path.basename(path))
    return okr, preds


runs = [summarise(p) for p in RUNS]
MAIN = ["clef rule@0.5", "clef composite@0.7", "qwen rule", "qwen own keep"]
cols = [(name, preds[name]) for _, preds in runs for name in MAIN if name in preds]
print("\n== disagreements with gold (~ = borderline gold label)")
print("id  gold   " + "  ".join(f"{n[:14]:<14}" for n, _ in cols) + "  nurl")
for i in sorted(gold):
    cells, wrong = [], False
    for _, p in cols:
        if i not in p:
            cells.append(f"{'-':<14}")
            continue
        cells.append(f"{'keep' if p[i] else 'drop':<14}")
        wrong |= p[i] != gold[i]["keep"]
    if wrong:
        g = "keep" if gold[i]["keep"] else "drop"
        b = "~" if gold[i]["border"] else " "
        print(f"{i:>3} {g}{b}   " + "  ".join(cells) + f"  {items[i]['nurl'][:60]}")
