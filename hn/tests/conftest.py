"""Shared fixtures: a tiny HN-shaped parquet dataset built in the test."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

# (id, type, by, time, text, parent, url, score, descendants, title)
# type: 1 story, 2 comment. Comments on story 100 recommend teachyourselfcs.com
# from three authors across three years; story 200 has two authors for a second URL.
ROWS = [
    (100, 1, "op", "2019-01-01 10:00:00", "", None, "https://www.teachyourselfcs.com/", 250, 3,
     "Teach Yourself Computer Science"),
    (200, 1, "op2", "2020-02-02 10:00:00", "", None, "https://example.org/post", 40, 2,
     "A post"),
    (101, 2, "alice", "2019-01-01 11:00:00",
     'I highly recommend <a href="https:&#x2F;&#x2F;teachyourselfcs.com&#x2F;">this</a>',
     100, "", None, None, ""),
    (102, 2, "bob", "2020-05-01 11:00:00",
     'Reply: great resource, see <a href="http://www.teachyourselfcs.com">it</a>',
     101, "", None, None, ""),
    (103, 2, "carol", "2021-06-01 11:00:00",
     'Deep reply <p>worth reading <a href="https://teachyourselfcs.com/#top">link</a>',
     102, "", None, None, ""),
    (104, 2, "dave", "2021-06-02 11:00:00",
     'no recommendation phrase <a href="https://teachyourselfcs.com/">link</a>',
     100, "", None, None, ""),
    (201, 2, "erin", "2020-02-02 12:00:00",
     'I recommend <a href="https://example.org/post?utm=1">this post</a>',
     200, "", None, None, ""),
    (202, 2, "frank", "2022-02-02 12:00:00",
     'start with <a href="https://example.org/post">this</a>',
     200, "", None, None, ""),
    (203, 2, "gina", "2022-02-03 12:00:00",
     'highly recommend <a href="https://www.youtube.com/watch?v=1">video</a>',
     200, "", None, None, ""),
    (204, 2, "hank", "2022-02-04 12:00:00",
     'highly recommend <a href="https://www.youtube.com/watch?v=1">video</a>',
     200, "", None, None, ""),
    (205, 2, "ivy", "2022-02-05 12:00:00",
     'highly recommend <a href="https://www.youtube.com/watch?v=1">video</a>',
     200, "", None, None, ""),
    (300, 2, "orphan", "2022-03-01 12:00:00", "parent missing", 999, "", None, None, ""),
]


@pytest.fixture
def dataset_dir(tmp_path: Path) -> Path:
    """Two monthly parquet files under dataset/data/YYYY/, like the real layout."""
    root = tmp_path / "dataset"
    con = duckdb.connect()
    con.execute("""CREATE TABLE t (id BIGINT, type TINYINT, "by" VARCHAR, time TIMESTAMP,
                   text VARCHAR, parent BIGINT, url VARCHAR, score INTEGER,
                   descendants INTEGER, title VARCHAR, dead BOOLEAN, deleted BOOLEAN)""")
    for r in ROWS:
        con.execute("INSERT INTO t VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, false, false)", list(r))
    for year, cond in (("2019", "year(time) <= 2019"), ("2020", "year(time) >= 2020")):
        d = root / "data" / year
        d.mkdir(parents=True)
        con.execute(f"COPY (SELECT * FROM t WHERE {cond}) TO '{d / (year + '-01.parquet')}'")
    return root
