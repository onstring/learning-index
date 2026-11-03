import json

from hnlearn import assemble, jsonl, rubric


def cand(nurl, ppl=3, yrs=2, story=True):
    return {"nurl": nurl, "host": nurl.split("/")[0], "ppl": ppl, "yrs": yrs, "y0": 2019,
            "y1": 2020, "mentions": ppl,
            "evidence": [{"id": 11, "author": "alice", "date": "2019-01-01", "root_id": 100,
                          "root_title": "Thread", "excerpt": "I recommend it"}],
            "story_id": 100 if story else None, "story_title": "Story" if story else None,
            "story_score": 50 if story else None}


def fetched(nurl, status=200, title="Page | Site", final_url=None, url=None):
    return {"nurl": nurl, "url": url or f"https://{nurl}", "status": status, "error": None,
            "final_url": final_url or f"https://{nurl}/", "title": title, "description": None,
            "snippet": None}


def clef(nurl, composite=0.9, topic="programming", rtype="course", difficulty=1.4):
    row = {"nurl": nurl, rubric.COMPOSITE[0]: composite, "topic": topic,
           "resource_type": rtype, "difficulty": difficulty}
    for name, *_ in rubric.BOOLS:
        row[name] = 0.5
    return row


def blurb(nurl, title="Nice Title", text="Learn things."):
    return {"nurl": nurl, "title": title, "blurb": text}


def write(tmp_path, cands, fetch, clefs, blurbs):
    paths = {}
    for name, rows in (("c", cands), ("f", fetch), ("k", clefs), ("b", blurbs)):
        p = tmp_path / f"{name}.jsonl"
        for r in rows:
            jsonl.append(p, r)
        paths[name] = p
    return paths


def test_assemble_joins_and_ranks(tmp_path):
    p = write(tmp_path,
              [cand("a.com", ppl=5), cand("b.com/x", ppl=9), cand("c.com", ppl=3),
               cand("dead.com", ppl=7), cand("unclassified.com", ppl=7)],
              [fetched("a.com"), fetched("b.com/x"), fetched("c.com"), fetched("dead.com", 404),
               fetched("unclassified.com")],
              [clef("a.com"), clef("b.com/x", topic="web"), clef("c.com", composite=0.3),
               clef("dead.com")],
              [blurb("a.com"), blurb("b.com/x", "B Title", "Learn B.")])
    out = tmp_path / "resources.json"
    stats = assemble.run(p["c"], p["f"], p["k"], p["b"], out)
    assert stats == {"candidates": 5, "classified": 4, "kept": 2, "dropped": 1,
                     "dead": 1, "missing_blurb": 0}
    doc = json.loads(out.read_text())
    assert [r["nurl"] for r in doc["resources"]] == ["b.com/x", "a.com"]
    b = doc["resources"][0]
    assert b["rank"] == 1 and b["title"] == "B Title" and b["blurb"] == "Learn B."
    assert b["topic"] == "web" and b["topic_label"] == "Web development"
    assert b["resource_type"] == "course" and b["type_label"] == "Course"
    assert b["difficulty"] == 1 and b["difficulty_label"] == "Intermediate"
    assert b["url"] == "https://b.com/x/" and b["slug"] == "b-com-x"
    assert b["story"] == {"id": 100, "title": "Story", "score": 50,
                          "url": "https://news.ycombinator.com/item?id=100"}
    ev = b["evidence"][0]
    assert ev["comment_url"] == "https://news.ycombinator.com/item?id=11"
    assert ev["author"] == "alice" and ev["root_title"] == "Thread"
    assert doc["topics"][0] == {"key": "programming", "label": "Programming", "count": 1}
    assert {t["key"] for t in doc["topics"]} == {"programming", "web"}
    assert doc["site"]["name"] and doc["generated_at"]


def test_title_and_url_fallbacks(tmp_path):
    p = write(tmp_path,
              [cand("a.com", story=True), cand("b.com", story=False), cand("c.com", story=False)],
              [fetched("a.com", status=403, title=None, final_url=None),
               fetched("b.com", title="B Page", final_url="javascript:alert(1)",
                       url="http://b.com"),
               fetched("c.com", title=None, final_url=None)],
              [clef("a.com"), clef("b.com"), clef("c.com")], [])
    out = tmp_path / "r.json"
    stats = assemble.run(p["c"], p["f"], p["k"], p["b"], out)
    assert stats["missing_blurb"] == 3
    by = {r["nurl"]: r for r in json.loads(out.read_text())["resources"]}
    assert by["a.com"]["title"] == "Story" and by["a.com"]["url"] == "https://a.com"
    assert by["a.com"]["blurb"] == "" and by["a.com"]["unverified"] is True
    assert by["b.com"]["title"] == "B Page" and by["b.com"]["url"] == "http://b.com"
    assert by["c.com"]["title"] == "c.com"


def test_junk_titles_fall_through():
    c = cand("a.com", story=True)
    assert assemble.display_title(c, {"title": "One moment, please..."}, None) == "Story"
    junk_blurb = {"title": "Just a moment..."}
    assert assemble.display_title(c, {"title": "Real Page"}, junk_blurb) == "Real Page"


def test_slug_collisions_get_suffix():
    slugs = assemble.unique_slugs(["a.com/x", "a.com/x/", "a.com-x", "b.com"])
    assert slugs["b.com"] == "b-com"
    assert slugs["a.com/x"] == "a-com-x"
    assert slugs["a.com/x/"] != slugs["a.com/x"] and slugs["a.com/x/"].startswith("a-com-x-")
    assert len(set(slugs.values())) == 4


def test_assemble_rejects_missing_candidate_for_clef_row(tmp_path):
    p = write(tmp_path, [], [fetched("a.com")], [clef("a.com")], [])
    try:
        assemble.run(p["c"], p["f"], p["k"], p["b"], tmp_path / "r.json")
    except ValueError as e:
        assert "a.com" in str(e)
    else:
        raise AssertionError("expected ValueError")
