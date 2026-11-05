import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build  # noqa: E402


@pytest.fixture
def site(tmp_path):
    (tmp_path / "hn").mkdir()
    (tmp_path / "hn" / "search.json").write_text(json.dumps([{"t": "a"}, {"t": "b"}]))
    (tmp_path / "reddit").mkdir()
    (tmp_path / "reddit" / "meta.json").write_text(json.dumps({"periods": [
        {"key": "all-time", "label": "All time", "top": 70, "more": 85},
        {"key": "past-year", "label": "Past year", "top": 11, "more": 21}]}))
    return tmp_path


def test_hub_links_both_sections_with_live_counts(site):
    build.build(site, today=date(2026, 11, 5))
    html = (site / "index.html").read_text(encoding="utf-8")
    assert 'href="hn/index.html"' in html and 'href="reddit/index.html"' in html
    assert "2 free learning resources" in html
    assert "155 posts from all time" in html and "32 from the past year" in html
    assert '<aside class="side">' in html and "5 November 2026" in html
    assert "__" not in html
    # shared theme copied to the site root; .nojekyll so Pages serves files as-is
    assert (site / "style.css").read_bytes() == build.THEME_CSS.read_bytes()
    assert (site / ".nojekyll").exists()


def test_hub_fails_when_a_section_is_not_built(tmp_path):
    with pytest.raises(SystemExit, match="search.json"):
        build.build(tmp_path)
