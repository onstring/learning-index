"""Stage 2: mine URLs that several distinct HN commenters recommended, with evidence."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import duckdb

from hnlearn import config, jsonl, sql

log = logging.getLogger(__name__)

EVIDENCE_FETCH = 8  # evidence rows pulled per URL before de-duplicating by author


def mine(db_path: Path, out_path: Path, *, min_people: int = config.MIN_PEOPLE,
         limit: int | None = None) -> int:
    """Write one JSONL row per qualifying URL (overwrites). Returns the row count."""
    con = duckdb.connect(str(db_path), read_only=True)
    _build_mentions(con)
    _build_recs(con)
    _build_submissions(con)
    rows = con.execute(f"""
        SELECT r.nurl, r.host, r.ppl, r.yrs, r.y0, r.y1, r.mentions, r.evidence,
               s.id AS story_id, s.title AS story_title, s.score AS story_score
        FROM rec r LEFT JOIN sub s USING (nurl)
        WHERE r.ppl >= ? AND {sql.noise_filter('r.host')} AND r.host LIKE '%.%'
        ORDER BY r.ppl DESC, r.yrs DESC, r.nurl
        {'LIMIT ' + str(int(limit)) if limit else ''}""", [min_people]).fetchall()
    cols = ["nurl", "host", "ppl", "yrs", "y0", "y1", "mentions", "evidence",
            "story_id", "story_title", "story_score"]
    if out_path.exists():
        out_path.unlink()
    for raw in rows:
        row: dict[str, Any] = dict(zip(cols, raw, strict=True))
        row["evidence"] = dedupe_evidence(row["evidence"], config.MAX_EXCERPTS)
        jsonl.append(out_path, row)
    log.info("candidates: %d URLs with %d+ recommenders", len(rows), min_people)
    return len(rows)


def dedupe_evidence(evidence: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Keep the first evidence row per author, up to ``limit`` rows, preserving order."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for ev in evidence:
        if ev["author"] in seen:
            continue
        seen.add(ev["author"])
        out.append(ev)
        if len(out) == limit:
            break
    return out


def _build_mentions(con: duckdb.DuckDBPyConnection) -> None:
    excerpt = sql.UNESC.format(h=sql.STRIP.format(t="c.text"))
    con.execute(f"""CREATE TEMP TABLE mention AS
        SELECT c.id, c.author, strftime(c.time, '%Y-%m-%d') AS date, year(c.time) AS yr,
               {sql.NORM.format(u=sql.UNESC.format(h='t.h'))} AS nurl,
               left(trim({excerpt}), {config.EXCERPT_CHARS}) AS excerpt,
               cr.root AS root_id, st.title AS root_title
        FROM link_comments c
        LEFT JOIN comment_root cr ON cr.id = c.id
        LEFT JOIN stories st ON st.id = cr.root,
        unnest(regexp_extract_all(c.text, {sql.HREF}, 1)) AS t(h)
        WHERE NOT c.dead AND NOT c.deleted
          AND regexp_matches(c.text, {sql.literal(sql.REC_REGEX)})""")


def _build_recs(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(f"""CREATE TEMP TABLE rec AS
        SELECT nurl, {sql.HOST.format(n='nurl')} AS host, count(DISTINCT author) AS ppl,
               count(DISTINCT yr) AS yrs, min(yr) AS y0, max(yr) AS y1, count(*) AS mentions,
               list(struct_pack(id := id, author := author, date := date, root_id := root_id,
                                root_title := root_title, excerpt := excerpt)
                    ORDER BY length(excerpt) DESC, id)[1:{EVIDENCE_FETCH}] AS evidence
        FROM mention WHERE nurl <> '' GROUP BY 1""")


def _build_submissions(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(f"""CREATE TEMP TABLE sub AS
        SELECT {sql.NORM.format(u='url')} AS nurl, arg_max(title, score) AS title,
               max(score) AS score, arg_max(id, score) AS id
        FROM stories WHERE url <> '' AND NOT dead GROUP BY 1""")
