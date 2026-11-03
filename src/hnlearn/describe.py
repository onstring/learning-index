"""Stage 5: one-sentence blurb and clean title for every kept resource, from qwen3."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from hnlearn import config, jsonl, ollama, rubric, text

log = logging.getLogger(__name__)

TITLE_CHARS = 120
BLURB_CHARS = 300


def errors_path(out_path: Path) -> Path:
    return out_path.with_suffix(".errors.jsonl")


def run(candidates_path: Path, fetch_path: Path, clef_path: Path, out_path: Path, *,
        limit: int | None = None, model: str = config.BLURB_MODEL,
        threshold: float = config.KEEP_THRESHOLD,
        transport: ollama.Transport | None = None) -> dict[str, int]:
    """Describe kept rows not yet in ``out_path``. Failures retry next run. Returns counts."""
    cands = {row["nurl"]: row for row in jsonl.read(candidates_path)}
    fetched = {row["nurl"]: row for row in jsonl.read(fetch_path)}
    done = jsonl.done_keys(out_path, "nurl")
    stats = {"described": 0, "skipped_dropped": 0, "failed": 0}
    for clef in jsonl.read(clef_path):
        nurl = clef["nurl"]
        if nurl in done:
            continue
        if not rubric.keep(clef[rubric.COMPOSITE[0]], threshold):
            stats["skipped_dropped"] += 1
            continue
        if limit is not None and stats["described"] + stats["failed"] >= limit:
            break
        if nurl not in cands:
            raise ValueError(f"clef row for unknown candidate {nurl}; rerun candidates first")
        _describe_one(cands[nurl], fetched.get(nurl), model, out_path, transport, stats)
        if (stats["described"] + stats["failed"]) % 50 == 0:
            log.info("describe: %s", stats)
    return stats


def _describe_one(cand: dict[str, Any], page: dict[str, Any] | None, model: str,
                  out_path: Path, transport: ollama.Transport | None,
                  stats: dict[str, int]) -> None:
    user = rubric.state_text(cand, page)
    t0 = time.monotonic()
    try:
        reply = ollama.chat_json(model, rubric.blurb_system(), user, rubric.blurb_schema(),
                                 transport=transport)
        cleaned = clean_reply(reply.data)
    except (ollama.OllamaError, ValueError) as e:
        stats["failed"] += 1
        jsonl.append(errors_path(out_path), {"nurl": cand["nurl"], "error": str(e)[:300]})
        log.warning("describe %s failed: %s", cand["nurl"], e)
        return
    jsonl.append(out_path, {"nurl": cand["nurl"], "model": model,
                            "latency": round(time.monotonic() - t0, 2), **cleaned,
                            "usage": reply.usage})
    stats["described"] += 1


def clean_reply(data: dict[str, Any]) -> dict[str, str]:
    """Validate and trim the model's title and blurb; raise ValueError when unusable."""
    title = str(data.get("title") or "").strip()
    blurb = str(data.get("blurb") or "").strip()
    if not title:
        raise ValueError("empty title in reply")
    if not blurb:
        raise ValueError("empty blurb in reply")
    return {"title": text.truncate(title, TITLE_CHARS), "blurb": text.truncate(blurb, BLURB_CHARS)}
