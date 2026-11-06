import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "classify"))
import render  # noqa: E402

FIELDS = ["subreddit", "rank", "category", "learning_value", "scope", "topics",
          "takeaway", "title", "post_url", "reason", "id"]
EVIL = "</script><script>alert(1)</script>"


def write_csv(path: Path, rows: list[dict]) -> Path:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    return path


def row(pid: str, score: int, sub: str = "Bogleheads", title: str = "Title") -> dict:
    return {"subreddit": sub, "rank": "3", "category": "education",
            "learning_value": str(score), "scope": "investing", "topics": "tax; fees",
            "takeaway": "Lesson", "title": title,
            "post_url": f"https://www.reddit.com/r/{sub}/comments/{pid}/",
            "reason": "r", "id": pid}


@pytest.fixture
def sets(tmp_path):
    top = write_csv(tmp_path / "top.csv", [row("a", 5, title=EVIL), row("b", 4, sub="LETFs")])
    more = write_csv(tmp_path / "more.csv", [row("c", 3)])
    year = write_csv(tmp_path / "year.csv", [row("a", 4)])
    empty = write_csv(tmp_path / "none.csv", [])
    return [["All time", str(top), str(more)], ["Past year", str(year), str(empty)]]


def data_of(html: str) -> dict:
    blob = re.search(r'<script id="data" type="application/json">(.*?)</script>',
                     html, re.S).group(1)
    return json.loads(blob)


def test_render_writes_page_and_shared_theme(sets, tmp_path):
    out = tmp_path / "site" / "reddit"
    stats = render.render(sets, out, today=date(2026, 11, 5))
    assert stats == {"periods": 2, "posts": 4}
    html = (out / "index.html").read_text(encoding="utf-8")
    # shared theme copied in verbatim and cache-busted
    assert (out / "style.css").read_bytes() == render.THEME_CSS.read_bytes()
    assert (out / "reddit.css").exists()
    assert re.search(r'href="style.css\?v=[0-9a-f]{12}"', html)
    # same sidebar shell as the HN site, with links to the hub and the HN section
    assert '<aside class="side">' in html and 'class="brand"' in html
    assert 'href="../index.html"' in html and 'href="../hn/index.html"' in html
    assert "__" not in re.sub(r"<script.*?</script>", "", html, flags=re.S)
    assert "5 November 2026" in html


def test_post_text_cannot_break_out_of_the_data_block(sets, tmp_path):
    out = tmp_path / "r"
    render.render(sets, out)
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "<script><script>alert" not in html and "alert(1)" in html
    data = data_of(html)
    assert data["posts"][0]["title"] == EVIL


def test_periods_get_slug_keys_and_counts(sets, tmp_path):
    out = tmp_path / "r"
    render.render(sets, out)
    data = data_of((out / "index.html").read_text(encoding="utf-8"))
    assert data["periods"] == [
        {"key": "all-time", "label": "All time", "top": 2, "more": 1},
        {"key": "past-year", "label": "Past year", "top": 1, "more": 0}]
    assert {p["period"] for p in data["posts"]} == {"all-time", "past-year"}
    assert data["posts"][0]["topics"] == ["tax", "fees"]
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["periods"] == data["periods"]


def test_favourites_are_wired_for_client_side_storage(sets, tmp_path):
    out = tmp_path / "r"
    render.render(sets, out)
    html = (out / "index.html").read_text(encoding="utf-8")
    data = data_of(html)
    # every post carries its Reddit id, the key a favourite is stored under
    assert [p["id"] for p in data["posts"]] == ["a", "b", "c", "a"]
    assert "reddit:favourites" in html and "localStorage" in html
    assert 'href="#fav"' in html and 'id="fav-count"' in html
    assert "data-fav" in html and "this browser" in html


def test_cards_link_to_reddit_chinese_translation(sets, tmp_path):
    out = tmp_path / "r"
    render.render(sets, out)
    html = (out / "index.html").read_text(encoding="utf-8")
    # Reddit serves its own machine translation when ?tl=<lang> is added to a post URL
    assert 'TL_LANG = "zh-hans"' in html
    assert 'searchParams.set("tl", TL_LANG)' in html


def test_missing_period_data_fails_loudly(tmp_path):
    with pytest.raises(SystemExit, match="no posts"):
        render.render([["X", str(tmp_path / "a.csv"), str(tmp_path / "b.csv")]], tmp_path / "o")
