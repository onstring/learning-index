import json

from hnlearn import jsonl, site

EVIL = "<script>alert(1)</script>"


def resource(nurl, slug, rank, topic="programming", title="Title", blurb="Blurb",
             rtype="course", difficulty=0):
    labels = {"course": "Course", "explainer": "Explainer"}
    return {"nurl": nurl, "host": nurl.split("/")[0], "url": f"https://{nurl}",
            "unverified": rank == 2, "title": title, "blurb": blurb, "topic": topic,
            "topic_label": "Programming" if topic == "programming" else "Web development",
            "resource_type": rtype, "type_label": labels[rtype], "difficulty": difficulty,
            "difficulty_label": ["Beginner", "Intermediate", "Advanced"][difficulty],
            "keep_prob": 0.9, "ppl": 5, "yrs": 3, "y0": 2018,
            "y1": 2020, "mentions": 6, "rank": rank, "slug": slug,
            "evidence": [{"author": "alice", "date": "2019-01-01", "excerpt": f"Rec {EVIL}",
                          "comment_url": "https://news.ycombinator.com/item?id=11",
                          "root_title": "Thread", "root_url": "https://news.ycombinator.com/item?id=1"}],
            "story": {"id": 1, "title": "Story", "score": 50,
                      "url": "https://news.ycombinator.com/item?id=1"} if rank == 1 else None}


def model():
    return {"generated_at": "2026-11-03T00:00:00+00:00",
            "site": {"name": "HN Learning Index", "tagline": "Tag", "keep_threshold": 0.7,
                     "min_people": 3, "translate_label": "中文"},
            "topics": [{"key": "programming", "label": "Programming", "count": 1},
                       {"key": "web", "label": "Web development", "count": 1}],
            "resources": [resource("a.com", "a-com", 1, title=f"A {EVIL}"),
                          resource("b.com/x", "b-com-x", 2, topic="web", rtype="explainer",
                                   difficulty=2)]}


def build(tmp_path):
    src = tmp_path / "resources.json"
    jsonl.write_json(src, model())
    out = tmp_path / "site"
    return site.render(src, out), out


def test_render_writes_all_pages_and_escapes(tmp_path):
    stats, out = build(tmp_path)
    # index, about, all, 2 topics, 2 types, 2 levels, 2 resources
    assert stats == {"resources": 2, "topics": 2, "pages": 11}
    for name in ("index.html", "about.html", "all.html", "topics/programming.html",
                 "topics/web.html", "types/course.html", "types/explainer.html",
                 "levels/beginner.html", "levels/advanced.html", "r/a-com.html",
                 "r/b-com-x.html", "search.json", "style.css", "site.js"):
        assert (out / name).exists(), name
    index = (out / "index.html").read_text(encoding="utf-8")
    assert EVIL not in index and "&lt;script&gt;" in index
    assert 'href="topics/programming.html"' in index and 'href="r/a-com.html"' in index
    assert 'href="types/course.html"' in index and 'href="levels/advanced.html"' in index
    assert 'data-type="course"' in index and 'data-level="beginner"' in index
    assert '<select name="type">' in index and '<select name="level">' in index
    page = (out / "r/a-com.html").read_text(encoding="utf-8")
    assert EVIL not in page and "Rec &lt;script&gt;" in page
    assert 'href="../style.css"' in page and 'href="../topics/programming.html"' in page
    assert 'href="https://a.com"' in page and "news.ycombinator.com/user?id=alice" in page
    assert "50 points" in page
    assert ("https://translate.google.com/translate?sl=auto&amp;tl=zh-CN&amp;u=https%3A%2F%2Fa.com"
            in page)
    assert 'href="../style.css?v=20261103' in page
    unverified = (out / "r/b-com-x.html").read_text(encoding="utf-8")
    assert "could not verify" in unverified.lower()
    search = json.loads((out / "search.json").read_text(encoding="utf-8"))
    assert search[0]["u"] == "r/a-com.html" and search[1]["k"] == "web"


def test_facet_pages_list_matching_resources_and_mark_active(tmp_path):
    _, out = build(tmp_path)
    course = (out / "types/course.html").read_text(encoding="utf-8")
    assert 'href="../r/a-com.html"' in course and 'href="../r/b-com-x.html"' not in course
    assert '<select name="type">' not in course and '<select name="level">' in course
    assert 'class="active"' in course
    advanced = (out / "levels/advanced.html").read_text(encoding="utf-8")
    assert 'href="../r/b-com-x.html"' in advanced and "1 resources" in advanced
    all_page = (out / "all.html").read_text(encoding="utf-8")
    assert all_page.count('<article class="card"') == 2


def test_about_page_has_no_implementation_details(tmp_path):
    _, out = build(tmp_path)
    about = (out / "about.html").read_text(encoding="utf-8").lower()
    for word in ("clef", "qwen", "ollama", "regex", "0.7", "model"):
        assert word not in about, word
    assert "odc" in about or "open data commons" in about


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
