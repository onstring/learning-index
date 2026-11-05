"""Command line entry point: ``python -I -m hnlearn <stage> [--limit N]``."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from pathlib import Path

from hnlearn import assemble, build_db, candidates, classify, config, describe, fetch, site

Stage = Callable[[argparse.Namespace], None]
log = logging.getLogger(__name__)


def _build_db(_: argparse.Namespace) -> None:
    stats = build_db.build(config.DATASET_DIR, config.DB_PATH)
    print(", ".join(f"{k}={v:,}" for k, v in stats.items()))


def _candidates(args: argparse.Namespace) -> None:
    n = candidates.mine(config.DB_PATH, config.CANDIDATES_PATH, min_people=args.min_people,
                        limit=args.limit)
    log.info("candidates written; downstream stages pick up new URLs on their next run")
    print(f"{n:,} candidates -> {config.CANDIDATES_PATH}")


def _fetch(args: argparse.Namespace) -> None:
    n = fetch.run(config.CANDIDATES_PATH, config.FETCH_PATH, limit=args.limit)
    print(f"fetched {n:,} -> {config.FETCH_PATH}")


def _classify(args: argparse.Namespace) -> None:
    stats = classify.run(config.CANDIDATES_PATH, config.FETCH_PATH, config.CLEF_PATH,
                         limit=args.limit)
    print(", ".join(f"{k}={v:,}" for k, v in stats.items()), f"-> {config.CLEF_PATH}")


def _describe(args: argparse.Namespace) -> None:
    stats = describe.run(config.CANDIDATES_PATH, config.FETCH_PATH, config.CLEF_PATH,
                         config.BLURBS_PATH, limit=args.limit)
    print(", ".join(f"{k}={v:,}" for k, v in stats.items()), f"-> {config.BLURBS_PATH}")


def _assemble(_: argparse.Namespace) -> None:
    stats = assemble.run(config.CANDIDATES_PATH, config.FETCH_PATH, config.CLEF_PATH,
                         config.BLURBS_PATH, config.RESOURCES_PATH)
    print(", ".join(f"{k}={v:,}" for k, v in stats.items()), f"-> {config.RESOURCES_PATH}")


def _site(args: argparse.Namespace) -> None:
    out = args.out or config.SITE_DIR
    stats = site.render(config.RESOURCES_PATH, out)
    print(", ".join(f"{k}={v:,}" for k, v in stats.items()), f"-> {out}/")


STAGES: dict[str, Stage] = {
    "build_db": _build_db,
    "candidates": _candidates,
    "fetch": _fetch,
    "classify": _classify,
    "describe": _describe,
    "assemble": _assemble,
    "site": _site,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hnlearn", description=__doc__)
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument("--limit", type=int, default=None, help="process only the first N rows")
    parser.add_argument("--min-people", type=int, default=config.MIN_PEOPLE,
                        help="candidates: minimum distinct recommenders")
    parser.add_argument("--out", type=Path, default=None,
                        help="site: output directory (default: site/)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(name)s %(message)s")
    try:
        STAGES[args.stage](args)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
