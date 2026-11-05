import json

import pytest

from hnlearn import jsonl


def test_append_and_read_roundtrip(tmp_path):
    p = tmp_path / "x.jsonl"
    jsonl.append(p, {"id": 1, "s": "é <b>"})
    jsonl.append(p, {"id": 2})
    assert list(jsonl.read(p)) == [{"id": 1, "s": "é <b>"}, {"id": 2}]
    assert p.read_text(encoding="utf-8").count("\n") == 2


def test_read_missing_file_is_empty(tmp_path):
    assert list(jsonl.read(tmp_path / "nope.jsonl")) == []


def test_done_keys(tmp_path):
    p = tmp_path / "x.jsonl"
    jsonl.append(p, {"nurl": "a.com"})
    jsonl.append(p, {"nurl": "b.com"})
    assert jsonl.done_keys(p, "nurl") == {"a.com", "b.com"}
    assert jsonl.done_keys(tmp_path / "nope.jsonl", "nurl") == set()


def test_read_rejects_malformed_line(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text('{"id": 1}\nnot json\n', encoding="utf-8")
    with pytest.raises(ValueError, match="bad.jsonl:2"):
        list(jsonl.read(p))


def test_torn_last_line_is_skipped_and_repaired_by_append(tmp_path):
    p = tmp_path / "torn.jsonl"
    p.write_text('{"id": 1}\n{"id": 2, "s": "cut off', encoding="utf-8")
    assert list(jsonl.read(p)) == [{"id": 1}]
    jsonl.append(p, {"id": 3})
    assert list(jsonl.read(p)) == [{"id": 1}, {"id": 3}]
    assert p.read_text(encoding="utf-8") == '{"id": 1}\n{"id": 3}\n'
    torn_only = tmp_path / "only.jsonl"
    torn_only.write_text('{"id": 1', encoding="utf-8")
    jsonl.append(torn_only, {"id": 2})
    assert list(jsonl.read(torn_only)) == [{"id": 2}]


def test_replace_with_is_atomic_and_counts(tmp_path):
    p = tmp_path / "x.jsonl"
    jsonl.append(p, {"old": True})
    assert jsonl.replace_with(p, ({"id": i} for i in range(3))) == 3
    assert [r["id"] for r in jsonl.read(p)] == [0, 1, 2]
    assert not p.with_name("x.jsonl.tmp").exists()


def test_require_keys():
    jsonl.require_keys({"a": 1, "b": 2}, ["a", "b"], "row 1")
    with pytest.raises(ValueError, match="row 7 missing: b"):
        jsonl.require_keys({"a": 1}, ["a", "b"], "row 7")


def test_write_json(tmp_path):
    p = tmp_path / "out" / "x.json"
    jsonl.write_json(p, {"k": [1, 2]})
    assert json.loads(p.read_text(encoding="utf-8")) == {"k": [1, 2]}
