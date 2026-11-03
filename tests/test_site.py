import json

from hnlearn import jsonl, site

EVIL = "<script>alert(1)</script>"


def resource(nurl, slug, rank, topic="programming", title="Title", blurb="Blurb"):
    return {"nurl": nurl, "host": nurl.split("/")[0], "url": f"https://{nurl}",
            "unverified": rank == 2, "title": title, "blurb": blurb, "topic": topic,
            "topic_label": "Programming" if topic == "programming" else "Web development",
            "resource_type": "course", "type_label": "Course", "difficulty": 0,
            "difficulty_label": "Beginner", "keep_prob": 0.9, "ppl": 5, "yrs": 3, "y0": 2018,
            "y1": 2020, "mentions": 6, "rank": rank, "slug": slug,
            "evidence": [{"author": "alice", "date": "2019-01-01", "excerpt": f"Rec {EVIL}",
                          "comment_url": "https://news.ycombinator.com/item?id=11",
                          "root_title": "Thread", "root_url": "https://news.ycombinator.com/item?id=1"}],
            "story": {"id": 1, "title": "Story", "score": 50,
                      "url": "https://news.ycombinator.com/item?id=1"} if rank == 1 else None}


def model():
    return {"generated_at": "2026-11-03T00:00:00+00:00",
            "site": {"name": "HN Learning Index", "tagline": "Tag", "keep_threshold": 0.7,
                     "min_people": 3},
            "topics": [{"key": "programming", "label": "Programming", "count": 1},
                       {"key": "web", "label": "Web development", "count": 1}],
            "resources": [resource("a.com", "a-com", 1, title=f"A {EVIL}"),
                          resource("b.com/x", "b-com-x", 2, topic="web")]}


def test_render_writes_all_pages_and_escapes(tmp_path):
    src = tmp_path / "resources.json"
    jsonl.write_json(src, model())
    out = tmp_path / "site"
    stats = site.render(src, out)
    assert stats == {"resources": 2, "topics": 2, "pages": 6}
    for name in ("index.html", "about.html", "topics/programming.html", "topics/web.html",
                 "r/a-com.html", "r/b-com-x.html", "search.json", "style.css", "search.js"):
        assert (out / name).exists(), name
    index = (out / "index.html").read_text(encoding="utf-8")
    assert EVIL not in index and "&lt;script&gt;" in index
    assert 'href="topics/programming.html"' in index and 'href="r/a-com.html"' in index
    page = (out / "r/a-com.html").read_text(encoding="utf-8")
    assert EVIL not in page and "Rec &lt;script&gt;" in page
    assert 'href="../style.css"' in page and 'href="../topics/programming.html"' in page
    assert 'href="https://a.com"' in page and "news.ycombinator.com/user?id=alice" in page
    assert "50 points" in page
    unverified = (out / "r/b-com-x.html").read_text(encoding="utf-8")
    assert "could not verify" in unverified.lower()
    search = json.loads((out / "search.json").read_text(encoding="utf-8"))
    assert search[0]["u"] == "r/a-com.html" and search[1]["k"] == "web"


def test_render_removes_stale_pages(tmp_path):
    src = tmp_path / "resources.json"
    jsonl.write_json(src, model())
    out = tmp_path / "site"
    (out / "r").mkdir(parents=True)
    (out / "r" / "gone.html").write_text("old")
    site.render(src, out)
    assert not (out / "r" / "gone.html").exists() and (out / "r" / "a-com.html").exists()


def test_render_rejects_bad_model(tmp_path):
    src = tmp_path / "resources.json"
    jsonl.write_json(src, {"resources": []})
    try:
        site.render(src, tmp_path / "site")
    except ValueError as e:
        assert "topics" in str(e)
    else:
        raise AssertionError("expected ValueError")
