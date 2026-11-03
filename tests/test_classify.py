import urllib.error

from hnlearn import classify, jsonl, rubric

CAND = {"nurl": "a.com", "host": "a.com", "ppl": 3, "yrs": 2, "y0": 2019, "y1": 2020,
        "story_title": "A", "story_score": 10, "evidence": [{"author": "x", "excerpt": "rec"}]}
FETCHED = {"nurl": "a.com", "status": 200, "title": "A page", "description": None, "snippet": "t"}


def reply(composite=0.9, topic="programming"):
    answers = {name: {"type": "noul", "noul": 0.5} for name, *_ in rubric.BOOLS}
    answers[rubric.COMPOSITE[0]] = {"type": "noul", "noul": composite}
    answers["topic"] = {"type": "choice", "choice": topic, "probabilities": {topic: 1.0},
                        "confidence": 1.0}
    answers["resource_type"] = {"type": "choice", "choice": "course",
                                "probabilities": {"course": 1.0}, "confidence": 1.0}
    answers["difficulty"] = {"type": "score", "score": 0.4, "probabilities": {"0": 0.6, "1": 0.4},
                             "confidence": 0.3}
    return {"model": "clef-flash", "answers": answers,
            "usage": {"input_tokens": 100, "output_tokens": 0}}


class Transport:
    def __init__(self, replies):
        self.replies = list(replies)
        self.states = []

    def __call__(self, path, body, timeout):
        self.states.append(body["state"])
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _files(tmp_path, cands, fetched):
    c, f, o = tmp_path / "c.jsonl", tmp_path / "f.jsonl", tmp_path / "clef.jsonl"
    for row in cands:
        jsonl.append(c, row)
    for row in fetched:
        jsonl.append(f, row)
    return c, f, o


def test_run_classifies_live_rows_and_skips_dead_or_unfetched(tmp_path):
    dead = {**CAND, "nurl": "dead.com"}
    unfetched = {**CAND, "nurl": "later.com"}
    c, f, o = _files(tmp_path, [CAND, dead, unfetched],
                     [FETCHED, {"nurl": "dead.com", "status": 404}])
    t = Transport([reply()])
    stats = classify.run(c, f, o, transport=t)
    assert stats == {"classified": 1, "skipped_dead": 1, "skipped_unfetched": 1, "failed": 0}
    rows = list(jsonl.read(o))
    assert len(rows) == 1
    r = rows[0]
    assert r["nurl"] == "a.com" and r["is_free_learning_resource"] == 0.9
    assert r["topic"] == "programming" and r["resource_type"] == "course"
    assert r["difficulty"] == 0.4 and r["free_to_access"] == 0.5
    assert r["usage"]["input_tokens"] == 100 and r["latency"] >= 0
    assert "Page title: A page" in t.states[0] and "HN comment 1: rec" in t.states[0]


def test_run_resumes_and_limits(tmp_path):
    b = {**CAND, "nurl": "b.com"}
    c, f, o = _files(tmp_path, [CAND, b], [FETCHED, {**FETCHED, "nurl": "b.com"}])
    assert classify.run(c, f, o, limit=1, transport=Transport([reply()]))["classified"] == 1
    assert classify.run(c, f, o, transport=Transport([reply()]))["classified"] == 1
    assert [r["nurl"] for r in jsonl.read(o)] == ["a.com", "b.com"]
    assert classify.run(c, f, o, transport=Transport([]))["classified"] == 0


def test_run_records_failures_separately_and_retries_them(tmp_path):
    c, f, o = _files(tmp_path, [CAND], [FETCHED])
    err = urllib.error.URLError("down")
    assert classify.run(c, f, o, transport=Transport([err]))["failed"] == 1
    assert list(jsonl.read(o)) == []
    errors = list(jsonl.read(o.with_suffix(".errors.jsonl")))
    assert errors[0]["nurl"] == "a.com" and "down" in errors[0]["error"]
    assert classify.run(c, f, o, transport=Transport([reply()]))["classified"] == 1


def test_run_rejects_malformed_candidate(tmp_path):
    c, f, o = _files(tmp_path, [{"nurl": "a.com"}], [FETCHED])
    try:
        classify.run(c, f, o, transport=Transport([reply()]))
    except ValueError as e:
        assert "a.com" in str(e) and "ppl" in str(e)
    else:
        raise AssertionError("expected ValueError")
