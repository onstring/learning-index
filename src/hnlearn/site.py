"""Stage 7: render the static site from resources.json."""

from __future__ import annotations

import json
import logging
import shutil
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader

from hnlearn import config, jsonl, rubric

log = logging.getLogger(__name__)

HERE = Path(__file__).parent
MODEL_KEYS = ("generated_at", "site", "topics", "resources")
ASSETS = ("style.css", "site.js")
LEVEL_KEYS = tuple(label.lower() for label in rubric.DIFFICULTY_LABELS)


def render(resources_path: Path, out_dir: Path, *,
           home_limit: int = config.HOME_LIMIT) -> dict[str, int]:
    """Write every page, the search index and static assets. Returns counts."""
    model = json.loads(resources_path.read_text(encoding="utf-8"))
    jsonl.require_keys(model, MODEL_KEYS, "resources.json")
    resources = [{**r, "level": LEVEL_KEYS[r["difficulty"]]} for r in model["resources"]]
    facets = {"topics": model["topics"], "types": type_facet(resources),
              "levels": level_facet(resources)}
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=True,
                      trim_blocks=True, lstrip_blocks=True)
    env.globals.update(site=model["site"], facets=facets, generated_at=model["generated_at"],
                       total=len(resources), build_id=build_id(model["generated_at"]),
                       translate_url=translate_url)
    for stale in ("r", "topics", "types", "levels"):
        shutil.rmtree(out_dir / stale, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = _write(env, "index.html", out_dir / "index.html", root="",
                   resources=resources[:home_limit])
    pages += _write(env, "about.html", out_dir / "about.html", root="")
    pages += _write(env, "list.html", out_dir / "all.html", root="", heading="All resources",
                    intro="Every resource, most recommended first.", resources=resources)
    # Every card is rendered; the browser shows only those starred in localStorage.
    pages += _write(env, "favourites.html", out_dir / "favourites.html", root="",
                    resources=resources)
    pages += _facet_pages(env, out_dir, "topics", facets["topics"], resources, "topic")
    pages += _facet_pages(env, out_dir, "types", facets["types"], resources, "resource_type")
    pages += _facet_pages(env, out_dir, "levels", facets["levels"], resources, "level")
    for r in resources:
        pages += _write(env, "resource.html", out_dir / "r" / f"{r['slug']}.html", root="../",
                        r=r)
    jsonl.write_json(out_dir / "search.json", search_index(resources))
    for asset in ASSETS:
        shutil.copyfile(HERE / "static" / asset, out_dir / asset)
    stats = {"resources": len(resources), "topics": len(facets["topics"]), "pages": pages}
    log.info("site: %s -> %s", stats, out_dir)
    return stats


def _facet_pages(env: Environment, out_dir: Path, folder: str, facet: list[dict[str, Any]],
                 resources: list[dict[str, Any]], field: str) -> int:
    pages = 0
    for f in facet:
        rows = [r for r in resources if r[field] == f["key"]]
        pages += _write(env, "list.html", out_dir / folder / f"{f['key']}.html", root="../",
                        heading=f["label"], intro=f"{len(rows)} resources, most recommended first.",
                        resources=rows, active=(folder, f["key"]))
    return pages


def _write(env: Environment, template: str, path: Path, **ctx: Any) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(env.get_template(template).render(**ctx), encoding="utf-8")
    return 1


def type_facet(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(r["resource_type"] for r in resources)
    return [{"key": k, "label": rubric.TYPE_LABELS[k], "count": counts[k]}
            for k in rubric.TYPES if counts.get(k)]


def level_facet(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(r["level"] for r in resources)
    return [{"key": k, "label": label, "count": counts[k]}
            for k, label in zip(LEVEL_KEYS, rubric.DIFFICULTY_LABELS, strict=True)
            if counts.get(k)]


def build_id(generated_at: str) -> str:
    """Digits of the build timestamp, used to cache-bust the stylesheet and script."""
    return "".join(ch for ch in generated_at if ch.isdigit())[:14]


def translate_url(url: str, target: str = config.TRANSLATE_TARGET) -> str:
    """Google Translate link for a page, rendered in ``target`` (default Simplified Chinese)."""
    return f"https://translate.google.com/translate?sl=auto&tl={target}&u={quote(url, safe='')}"


def search_index(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compact records for client-side search."""
    return [{"t": r["title"], "b": r["blurb"], "h": r["host"], "k": r["topic"],
             "u": f"r/{r['slug']}.html"} for r in resources]
