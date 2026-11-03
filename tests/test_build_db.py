import duckdb

from hnlearn import build_db


def test_build_creates_tables_and_resolves_roots(dataset_dir, tmp_path):
    db = tmp_path / "hn.duckdb"
    stats = build_db.build(dataset_dir, db)
    assert stats["stories"] == 2
    assert stats["link_comments"] == 9  # every comment with an href, dead or not
    assert stats["comment_parents"] == 10
    con = duckdb.connect(str(db), read_only=True)
    roots = dict(con.execute("SELECT id, root FROM comment_root").fetchall())
    assert roots[101] == 100 and roots[102] == 100 and roots[103] == 100
    assert roots[201] == 200
    depth = dict(con.execute("SELECT id, depth FROM comment_root").fetchall())
    assert depth[103] == 3 and depth[101] == 1
    assert roots[300] == 999  # orphan keeps its last known ancestor
    assert con.execute("SELECT author FROM stories WHERE id=100").fetchone()[0] == "op"


def test_build_is_rerunnable(dataset_dir, tmp_path):
    db = tmp_path / "hn.duckdb"
    build_db.build(dataset_dir, db)
    stats = build_db.build(dataset_dir, db)
    assert stats["stories"] == 2


def test_build_fails_clearly_without_parquet(tmp_path):
    try:
        build_db.build(tmp_path / "empty", tmp_path / "x.duckdb")
    except FileNotFoundError as e:
        assert "parquet" in str(e)
    else:
        raise AssertionError("expected FileNotFoundError")
