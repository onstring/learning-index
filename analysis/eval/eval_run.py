"""Run one model over the eval items. Resumable; appends to out.jsonl.

Usage: python -I eval_run.py <items.jsonl> <backend: clef|qwen> <model> <out.jsonl>
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_rubric import BOOLS, COMPOSITE, DIFFICULTY, TOPICS, TYPES, state_text  # noqa: E402

ITEMS, BACKEND, MODEL, OUT = sys.argv[1:5]
BASE = "http://localhost:11434"


def post(path, body, timeout=600):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def clef_questions():
    q = {}
    for name, instr, t, f in BOOLS:
        q[name] = {"type": "noul", "instructions": instr, "criteria": {"true": t, "false": f}}
    name, instr, t, f = COMPOSITE
    q[name] = {"type": "noul", "instructions": instr, "criteria": {"true": t, "false": f}}
    q["topic"] = {"type": "choice", "instructions": "Primary topic of the resource.",
                  "criteria": dict(TOPICS)}
    q["resource_type"] = {"type": "choice", "instructions": "What kind of resource is it?",
                          "criteria": dict(TYPES)}
    q["difficulty"] = {"type": "score", "instructions": "Difficulty for a curious student.",
                       "criteria": list(DIFFICULTY)}
    return q


def run_clef(item):
    body = {"model": MODEL, "state": state_text(item), "questions": clef_questions(),
            "keep_alive": "10m"}
    r = post("/v1/systemone", body)
    a = r["answers"]
    out = {k: a[k]["noul"] for k in a if a[k]["type"] == "noul"}
    out["topic"] = a["topic"]["choice"]
    out["topic_probs"] = a["topic"]["probabilities"]
    out["resource_type"] = a["resource_type"]["choice"]
    out["difficulty"] = a["difficulty"]["score"]
    out["usage"] = r.get("usage")
    return out


def qwen_schema():
    props = {name: {"type": "boolean"} for name, *_ in BOOLS}
    props["keep"] = {"type": "boolean"}
    props["topic"] = {"type": "string", "enum": list(TOPICS)}
    props["resource_type"] = {"type": "string", "enum": list(TYPES)}
    props["difficulty"] = {"type": "integer", "minimum": 0, "maximum": 2}
    props["blurb"] = {"type": "string"}
    return {"type": "object", "properties": props, "required": list(props)}


def qwen_system():
    lines = ["You classify web resources recommended on Hacker News for a site that indexes free "
             "online learning resources for curious students. Answer every field strictly from "
             "the rubric below. Output JSON only.", "", "Boolean fields:"]
    for name, instr, t, f in BOOLS:
        lines += [f"- {name}: {instr} true = {t}. false = {f}."]
    lines += ["- keep: true only if free_to_access AND is_learning_material AND is_evergreen AND "
              "NOT is_video AND NOT is_code_repo AND NOT is_paid_book.", "",
              "topic (pick one):"] + [f"- {k}: {v}" for k, v in TOPICS.items()]
    lines += ["", "resource_type (pick one):"] + [f"- {k}: {v}" for k, v in TYPES.items()]
    lines += ["", "difficulty (integer):"] + [f"- {i}: {d}" for i, d in enumerate(DIFFICULTY)]
    lines += ["", "blurb: one neutral sentence (max 25 words) describing what a student would "
              "learn from the resource. Do not mention Hacker News."]
    return "\n".join(lines)


def run_qwen(item):
    body = {"model": MODEL, "stream": False, "think": BACKEND == "qwen_think",
            "format": qwen_schema(),
            "options": {"temperature": 0, "num_ctx": 8192}, "keep_alive": "10m",
            "messages": [{"role": "system", "content": qwen_system()},
                         {"role": "user", "content": state_text(item)}]}
    r = post("/api/chat", body)
    content = r["message"]["content"]
    out = json.loads(content)
    out["usage"] = {"input_tokens": r.get("prompt_eval_count"),
                    "output_tokens": r.get("eval_count")}
    return out


RUN = {"clef": run_clef, "qwen": run_qwen, "qwen_think": run_qwen}[BACKEND]
done = set()
if os.path.exists(OUT):
    done = {json.loads(l)["id"] for l in open(OUT)}
items = [json.loads(l) for l in open(ITEMS) if json.loads(l)["id"] not in done]
print(f"{BACKEND}/{MODEL}: {len(items)} to run, {len(done)} done", file=sys.stderr)
if items:  # warm-up call so latency excludes model load
    t0 = time.time()
    RUN(items[0])
    print(f"warm-up {time.time() - t0:.1f}s", file=sys.stderr)
with open(OUT, "a") as f:
    for n, item in enumerate(items, 1):
        t0 = time.time()
        try:
            res = RUN(item)
            rec = {"id": item["id"], "ok": True, "latency": time.time() - t0, **res}
        except Exception as e:  # noqa: BLE001 - record failure and continue
            rec = {"id": item["id"], "ok": False, "latency": time.time() - t0, "error": str(e)[:300]}
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        if n % 10 == 0:
            print(f"{n}/{len(items)} last {rec['latency']:.1f}s", file=sys.stderr)
print("done", file=sys.stderr)
