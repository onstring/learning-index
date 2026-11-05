"""Stage 4: score every fetched, live candidate with the clef-flash decision model."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from hnlearn import config, jsonl, ollama, rubric

log = logging.getLogger(__name__)

CANDIDATE_KEYS = ("nurl", "host", "ppl", "yrs", "y0", "y1", "evidence")


def errors_path(out_path: Path) -> Path:
    return out_path.with_suffix(".errors.jsonl")


def run(candidates_path: Path, fetch_path: Path, out_path: Path, *, limit: int | None = None,
        model: str = config.CLEF_MODEL,
        transport: ollama.Transport | None = None) -> dict[str, int]:
    """Classify candidates with a live fetch that are not yet in ``out_path``.

    Dead or unfetched candidates are skipped. Failures go to a sibling errors file and
    are retried on the next run. Returns counts.
    """
    fetched = {row["nurl"]: row for row in jsonl.read(fetch_path)}
    done = jsonl.done_keys(out_path, "nurl")
    stats = {"classified": 0, "skipped_dead": 0, "skipped_unfetched": 0, "failed": 0}
    questions = rubric.clef_questions()
    for cand in jsonl.read(candidates_path):
        jsonl.require_keys(cand, CANDIDATE_KEYS, f"candidate {cand.get('nurl')}")
        if cand["nurl"] in done:
            continue
        if limit is not None and stats["classified"] + stats["failed"] >= limit:
            break
        page = fetched.get(cand["nurl"])
        if page is None:
            stats["skipped_unfetched"] += 1
            continue
        if page.get("status") not in config.ELIGIBLE_STATUSES:
            stats["skipped_dead"] += 1
            continue
        _classify_one(cand, page, questions, model, out_path, transport, stats)
        if (stats["classified"] + stats["failed"]) % 50 == 0:
            log.info("classify: %s", stats)
    return stats


def _classify_one(cand: dict[str, Any], page: dict[str, Any], questions: dict[str, Any],
                  model: str, out_path: Path, transport: ollama.Transport | None,
                  stats: dict[str, int]) -> None:
    state = rubric.state_text(cand, page)
    t0 = time.monotonic()
    try:
        decision = ollama.systemone(model, state, questions, transport=transport)
        row = {"nurl": cand["nurl"], "model": model, "latency": round(time.monotonic() - t0, 2),
               **flatten_answers(decision.answers), "usage": decision.usage}
    except (ollama.OllamaError, KeyError, TypeError, ValueError) as e:
        stats["failed"] += 1
        jsonl.append(errors_path(out_path), {"nurl": cand["nurl"], "error": str(e)[:300]})
        log.warning("classify %s failed: %s", cand["nurl"], e)
        return
    jsonl.append(out_path, row)
    stats["classified"] += 1


def flatten_answers(answers: dict[str, Any]) -> dict[str, Any]:
    """One flat row from clef's answer object: probabilities, choices and scores.

    Raises ValueError on a probability outside [0, 1] or NaN; unknown choices become "other".
    """
    row: dict[str, Any] = {}
    for name, *_ in (*rubric.BOOLS, rubric.COMPOSITE):
        row[name] = _probability(name, answers[name]["noul"])
    for name, known in (("topic", rubric.TOPICS), ("resource_type", rubric.TYPES)):
        choice = answers[name]["choice"]
        row[name] = choice if choice in known else "other"
        row[name + "_probs"] = answers[name]["probabilities"]
        row[name + "_confidence"] = answers[name].get("confidence")
    score = float(answers["difficulty"]["score"])
    if not 0 <= score <= len(rubric.DIFFICULTY) - 1:
        raise ValueError(f"difficulty score out of range: {score}")
    row["difficulty"] = score
    row["difficulty_probs"] = answers["difficulty"].get("probabilities")
    return row


def _probability(name: str, value: Any) -> float:
    p = float(value)
    if not 0.0 <= p <= 1.0:  # also rejects NaN
        raise ValueError(f"{name}: probability out of range: {value!r}")
    return p
