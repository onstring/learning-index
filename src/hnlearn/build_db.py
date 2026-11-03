"""Stage 1: monthly parquet files to a DuckDB file with the tables the pipeline needs."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

log = logging.getLogger(__name__)

PARQUET_GLOB = "data/*/*.parquet"
MAX_DEPTH = 300  # deepest HN threads exceed 60 levels; iterations are cheap once few rows remain


def build(dataset_dir: Path, db_path: Path) -> dict[str, int]:
    """Create stories, link_comments, comment_parents and comment_root. Returns row counts."""
    if not list(dataset_dir.glob(PARQUET_GLOB)):
        raise FileNotFoundError(f"no parquet files under {dataset_dir / PARQUET_GLOB}")
    src = f"read_parquet('{dataset_dir / PARQUET_GLOB}')"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute("SET preserve_insertion_order=false")
    tables = {
        "stories": f"""SELECT id, "by" AS author, time, title, url, score, descendants, text,
                       coalesce(dead, false) AS dead, coalesce(deleted, false) AS deleted
                       FROM {src} WHERE type=1""",
        "link_comments": f"""SELECT id, "by" AS author, time, parent, text,
                             coalesce(dead, false) AS dead, coalesce(deleted, false) AS deleted
                             FROM {src} WHERE type=2 AND text LIKE '%href=%'""",
        "comment_parents": f"SELECT id, parent FROM {src} WHERE type=2",
    }
    stats: dict[str, int] = {}
    for name, select in tables.items():
        con.execute(f"CREATE OR REPLACE TABLE {name} AS {select}")
        stats[name] = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        log.info("%s: %s rows", name, f"{stats[name]:,}")
    stats["comment_root"] = resolve_roots(con)
    con.close()
    return stats


def resolve_roots(con: duckdb.DuckDBPyConnection) -> int:
    """Climb parent links until every comment points at a story (or its last known ancestor)."""
    con.execute("""CREATE OR REPLACE TABLE comment_root AS
                   SELECT id, parent AS root, 1 AS depth FROM comment_parents""")
    for i in range(1, MAX_DEPTH + 1):
        climbed = con.execute("""UPDATE comment_root cr SET root = cp.parent, depth = cr.depth + 1
                                 FROM comment_parents cp WHERE cr.root = cp.id""").fetchone()[0]
        log.info("resolve_roots iteration %d: climbed %s rows", i, f"{climbed:,}")
        if climbed == 0:
            break
    return con.execute("SELECT count(*) FROM comment_root").fetchone()[0]
