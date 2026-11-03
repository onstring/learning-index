"""Stage 7: render the static site from resources.json."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from hnlearn import config, jsonl

log = logging.getLogger(__name__)

HERE = Path(__file__).parent
MODEL_KEYS = ("generated_at", "site", "topics", "resources")


def render(resources_path: Path, out_dir: Path, *,
           home_limit: int = config.HOME_LIMIT) -> dict[str, int]:
    """Write every page, the search index and static assets. Returns counts."""
    model = json.loads(resources_path.read_text(encoding="utf-8"))
    jsonl.require_keys(model, MODEL_KEYS, "resources.json")
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=True,
                      trim_blocks=True, lstrip_blocks=True)
    env.globals.update(site=model["site"], topics=model["topics"],
                       generated_at=model["generated_at"])
    for stale in ("r", "topics"):  # resources dropped since the last build must disappear
        shutil.rmtree(out_dir / stale, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = 0
    pages += _write(env, "index.html", out_dir / "index.html", root="",
                    resources=model["resources"][:home_limit], total=len(model["resources"]))
    pages += _write(env, "about.html", out_dir / "about.html", root="")
    by_topic: dict[str, list[dict[str, Any]]] = {}
    for r in model["resources"]:
        by_topic.setdefault(r["topic"], []).append(r)
    for t in model["topics"]:
        pages += _write(env, "topic.html", out_dir / "topics" / f"{t['key']}.html", root="../",
                        topic=t, resources=by_topic.get(t["key"], []))
    for r in model["resources"]:
        pages += _write(env, "resource.html", out_dir / "r" / f"{r['slug']}.html", root="../",
                        r=r)
    jsonl.write_json(out_dir / "search.json", search_index(model["resources"]))
    for asset in ("style.css", "search.js"):
        shutil.copyfile(HERE / "static" / asset, out_dir / asset)
    stats = {"resources": len(model["resources"]), "topics": len(model["topics"]), "pages": pages}
    log.info("site: %s -> %s", stats, out_dir)
    return stats


def _write(env: Environment, template: str, path: Path, **ctx: Any) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(env.get_template(template).render(**ctx), encoding="utf-8")
    return 1


def search_index(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compact records for client-side search."""
    return [{"t": r["title"], "b": r["blurb"], "h": r["host"], "k": r["topic"],
             "u": f"r/{r['slug']}.html"} for r in resources]
