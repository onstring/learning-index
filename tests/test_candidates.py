from hnlearn import build_db, candidates, jsonl


def test_mine_finds_repeatedly_recommended_urls(dataset_dir, tmp_path):
    db = tmp_path / "hn.duckdb"
    build_db.build(dataset_dir, db)
    out = tmp_path / "candidates.jsonl"
    n = candidates.mine(db, out, min_people=3)
    rows = list(jsonl.read(out))
    assert n == 1 and len(rows) == 1
    r = rows[0]
    assert r["nurl"] == "teachyourselfcs.com" and r["host"] == "teachyourselfcs.com"
    assert r["ppl"] == 3 and r["yrs"] == 3 and (r["y0"], r["y1"]) == (2019, 2021)
    assert r["mentions"] == 3
    assert r["story_id"] == 100 and r["story_title"] == "Teach Yourself Computer Science"
    assert r["story_score"] == 250
    authors = [e["author"] for e in r["evidence"]]
    assert sorted(authors) == ["alice", "bob", "carol"]
    ev = {e["author"]: e for e in r["evidence"]}
    assert ev["carol"]["excerpt"] == "Deep reply worth reading link"
    assert ev["carol"]["root_id"] == 100 and ev["carol"]["root_title"].startswith("Teach")
    assert ev["alice"]["date"] == "2019-01-01" and ev["alice"]["id"] == 101


def test_mine_threshold_and_noise(dataset_dir, tmp_path):
    db = tmp_path / "hn.duckdb"
    build_db.build(dataset_dir, db)
    out = tmp_path / "c.jsonl"
    candidates.mine(db, out, min_people=2)
    urls = {r["nurl"] for r in jsonl.read(out)}
    assert urls == {"teachyourselfcs.com", "example.org/post"}  # youtube excluded


def test_mine_limit_and_overwrite(dataset_dir, tmp_path):
    db = tmp_path / "hn.duckdb"
    build_db.build(dataset_dir, db)
    out = tmp_path / "c.jsonl"
    candidates.mine(db, out, min_people=2, limit=1)
    assert len(list(jsonl.read(out))) == 1
    candidates.mine(db, out, min_people=2)
    assert len(list(jsonl.read(out))) == 2


def test_dedupe_evidence_keeps_one_per_author():
    ev = [{"author": "a", "excerpt": "long long"}, {"author": "a", "excerpt": "short"},
          {"author": "b", "excerpt": "x"}, {"author": "c", "excerpt": "y"},
          {"author": "d", "excerpt": "z"}]
    out = candidates.dedupe_evidence(ev, limit=3)
    assert [e["author"] for e in out] == ["a", "b", "c"]
