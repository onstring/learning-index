import json

from hnlearn import describe, jsonl

CAND = {"nurl": "a.com", "host": "a.com", "ppl": 3, "yrs": 2, "y0": 2019, "y1": 2020,
        "story_title": "A", "story_score": 10, "evidence": [{"author": "x", "excerpt": "rec"}]}
FETCHED = {"nurl": "a.com", "status": 200, "title": "A page | Site", "description": None,
           "snippet": "text"}


def clef_row(nurl, composite):
    return {"nurl": nurl, "is_free_learning_resource": composite, "topic": "programming"}


class Transport:
    def __init__(self, replies):
        self.replies = list(replies)
        self.bodies = []

    def __call__(self, path, body, timeout):
        self.bodies.append(body)
        return {"message": {"content": json.dumps(self.replies.pop(0))},
                "prompt_eval_count": 10, "eval_count": 5}


def _files(tmp_path, cands, fetched, clef):
    paths = [tmp_path / n for n in ("c.jsonl", "f.jsonl", "clef.jsonl")]
    for p, rows in zip(paths, (cands, fetched, clef), strict=True):
        for r in rows:
            jsonl.append(p, r)
    return (*paths, tmp_path / "blurbs.jsonl")


def test_run_describes_kept_rows_only(tmp_path):
    b = {**CAND, "nurl": "b.com"}
    c, f, k, o = _files(tmp_path, [CAND, b], [FETCHED, {**FETCHED, "nurl": "b.com"}],
                        [clef_row("a.com", 0.9), clef_row("b.com", 0.2)])
    t = Transport([{"title": "A page", "blurb": "Learn A."}])
    stats = describe.run(c, f, k, o, transport=t)
    assert stats == {"described": 1, "skipped_dropped": 1, "failed": 0}
    rows = list(jsonl.read(o))
    assert rows[0]["nurl"] == "a.com" and rows[0]["title"] == "A page"
    assert rows[0]["blurb"] == "Learn A." and rows[0]["usage"]["input_tokens"] == 10
    body = t.bodies[0]
    assert body["think"] is False and "Page title: A page | Site" in body["messages"][1]["content"]
    assert body["format"]["required"] == ["title", "blurb"]


def test_run_resumes_and_limits(tmp_path):
    b = {**CAND, "nurl": "b.com"}
    c, f, k, o = _files(tmp_path, [CAND, b], [FETCHED, {**FETCHED, "nurl": "b.com"}],
                        [clef_row("a.com", 0.9), clef_row("b.com", 0.9)])
    good = {"title": "T", "blurb": "B"}
    assert describe.run(c, f, k, o, limit=1, transport=Transport([good]))["described"] == 1
    assert describe.run(c, f, k, o, transport=Transport([good]))["described"] == 1
    assert [r["nurl"] for r in jsonl.read(o)] == ["a.com", "b.com"]


def test_run_rejects_bad_reply_and_retries(tmp_path):
    c, f, k, o = _files(tmp_path, [CAND], [FETCHED], [clef_row("a.com", 0.9)])
    stats = describe.run(c, f, k, o, transport=Transport([{"title": "", "blurb": "x"}]))
    assert stats["failed"] == 1 and list(jsonl.read(o)) == []
    err = list(jsonl.read(o.with_suffix(".errors.jsonl")))[0]
    assert err["nurl"] == "a.com" and "title" in err["error"]
    ok = describe.run(c, f, k, o, transport=Transport([{"title": "T", "blurb": "B"}]))
    assert ok["described"] == 1


def test_clean_reply_trims_and_limits():
    out = describe.clean_reply({"title": "  My Title  ", "blurb": " Learn things.  "})
    assert out == {"title": "My Title", "blurb": "Learn things."}
    long = describe.clean_reply({"title": "t" * 300, "blurb": "w " * 300})
    assert len(long["title"]) <= 123 and long["title"].endswith("...")
    assert len(long["blurb"]) <= 303
