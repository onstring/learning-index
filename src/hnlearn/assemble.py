"""Stage 6: join candidates, fetch, clef and blurb files into the site model."""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hnlearn import config, jsonl, rubric, text

log = logging.getLogger(__name__)

HN_ITEM = "https://news.ycombinator.com/item?id="


def run(candidates_path: Path, fetch_path: Path, clef_path: Path, blurbs_path: Path,
        out_path: Path, *, threshold: float = config.KEEP_THRESHOLD) -> dict[str, int]:
    """Write ``resources.json``. Returns counts of what was kept and why rows were dropped."""
    cands = {r["nurl"]: r for r in jsonl.read(candidates_path)}
    fetched = {r["nurl"]: r for r in jsonl.read(fetch_path)}
    blurbs = {r["nurl"]: r for r in jsonl.read(blurbs_path)}
    stats = {"candidates": len(cands), "classified": 0, "kept": 0, "dropped": 0, "dead": 0,
             "stale": 0, "missing_blurb": 0}
    kept: list[dict[str, Any]] = []
    for clef in jsonl.read(clef_path):
        stats["classified"] += 1
        nurl = clef["nurl"]
        if nurl not in cands:  # dropped by a later candidates run (for example a new noise host)
            stats["stale"] += 1
            continue
        page = fetched.get(nurl) or {}
        if not rubric.keep_row(clef, threshold):
            stats["dropped"] += 1
            continue
        if page.get("status") not in config.ELIGIBLE_STATUSES:
            stats["dead"] += 1
            continue
        blurb = blurbs.get(nurl)
        if blurb is None:
            stats["missing_blurb"] += 1
        kept.append(build_resource(cands[nurl], page, clef, blurb))
    kept.sort(key=lambda r: (-r["ppl"], -r["yrs"], r["nurl"]))
    slugs = unique_slugs([r["nurl"] for r in kept])
    resources = [{**r, "rank": i, "slug": slugs[r["nurl"]]} for i, r in enumerate(kept, 1)]
    stats["kept"] = len(resources)
    jsonl.write_json(out_path, {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "site": {"name": config.SITE_NAME, "tagline": config.SITE_TAGLINE,
                 "keep_threshold": threshold, "min_people": config.MIN_PEOPLE,
                 "translate_label": config.TRANSLATE_LABEL},
        "topics": topic_counts(resources),
        "resources": resources,
    })
    log.info("assemble: %s", stats)
    return stats


def build_resource(cand: dict[str, Any], page: dict[str, Any], clef: dict[str, Any],
                   blurb: dict[str, Any] | None) -> dict[str, Any]:
    """One site-ready record from the four stage rows."""
    difficulty = min(len(rubric.DIFFICULTY) - 1, max(0, int(clef["difficulty"] + 0.5)))
    story = None
    if cand.get("story_id"):
        story = {"id": cand["story_id"], "title": cand["story_title"],
                 "score": cand["story_score"], "url": f"{HN_ITEM}{cand['story_id']}"}
    return {
        "nurl": cand["nurl"], "host": cand["host"],
        "url": link_target(cand["nurl"], page),
        "unverified": page.get("status") != 200,
        "title": display_title(cand, page, blurb),
        "blurb": (blurb or {}).get("blurb", ""),
        "topic": clef["topic"], "topic_label": rubric.TOPIC_LABELS.get(clef["topic"], "Other"),
        "resource_type": clef["resource_type"],
        "type_label": rubric.TYPE_LABELS.get(clef["resource_type"], "Other"),
        "difficulty": difficulty, "difficulty_label": rubric.DIFFICULTY_LABELS[difficulty],
        "keep_prob": round(clef[rubric.COMPOSITE[0]], 3),
        "ppl": cand["ppl"], "yrs": cand["yrs"], "y0": cand["y0"], "y1": cand["y1"],
        "mentions": cand.get("mentions"),
        "evidence": [evidence_entry(e) for e in cand.get("evidence", [])],
        "story": story,
    }


def evidence_entry(ev: dict[str, Any]) -> dict[str, Any]:
    return {"author": ev["author"], "date": ev.get("date"), "excerpt": ev["excerpt"],
            "comment_url": f"{HN_ITEM}{ev['id']}", "root_title": ev.get("root_title"),
            "root_url": f"{HN_ITEM}{ev['root_id']}" if ev.get("root_id") else None}


def link_target(nurl: str, page: dict[str, Any]) -> str:
    """Where the resource link points.

    The post-redirect URL is used only when it stays on the same site, so a lapsed domain
    that now redirects to a parked page is not published as the live link.
    """
    final = page.get("final_url") or ""
    if page.get("status") == 200 and text.is_http_url(final) and same_site(nurl, final):
        return final
    if text.is_http_url(page.get("url") or ""):
        return page["url"]
    return f"https://{nurl}"


def same_site(nurl: str, url: str) -> bool:
    """True when ``url``'s host is the candidate's host, a subdomain of it, or its parent."""
    a = text.host_of(nurl)
    b = text.host_of(text.normalise_url(url))
    return bool(a and b) and (a == b or b.endswith("." + a) or a.endswith("." + b))


def display_title(cand: dict[str, Any], page: dict[str, Any], blurb: dict[str, Any] | None) -> str:
    """First usable of: blurb-model title, fetched page title, HN story title, the URL."""
    for candidate in ((blurb or {}).get("title"), page.get("title"), cand.get("story_title")):
        if candidate and candidate.strip() and not text.is_junk_title(candidate):
            return text.truncate(candidate.strip(), 120)
    return cand["nurl"]


def unique_slugs(nurls: list[str]) -> dict[str, str]:
    """Slug per URL in rank order; a later collision gets a short hash suffix."""
    out: dict[str, str] = {}
    taken: set[str] = set()
    for nurl in nurls:
        slug = text.slugify(nurl, maxlen=72) or "resource"
        if slug in taken:
            slug = f"{slug}-{hashlib.sha1(nurl.encode()).hexdigest()[:6]}"  # noqa: S324
        taken.add(slug)
        out[nurl] = slug
    return out


def topic_counts(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(r["topic"] for r in resources)
    return [{"key": k, "label": rubric.TOPIC_LABELS[k], "count": counts[k]}
            for k in rubric.TOPICS if counts.get(k)]
