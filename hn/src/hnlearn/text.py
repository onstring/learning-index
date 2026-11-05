"""Text helpers: HTML to text, URL normalisation, slugs. Pure functions, no I/O."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

# content inside these tags is dropped entirely
SKIP_TAGS = frozenset({"script", "style", "nav", "header", "footer", "noscript", "svg",
                       "template", "title", "iframe"})
# these tags separate words; inline tags such as <i> or <a> do not
BLOCK_TAGS = frozenset({"p", "br", "div", "li", "ul", "ol", "tr", "td", "th", "h1", "h2", "h3",
                        "h4", "h5", "h6", "section", "article", "main", "aside", "blockquote",
                        "pre", "table", "hr", "dd", "dt", "dl", "form", "figure", "figcaption"})
_WS = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]+>")
_HTTP_URL = re.compile(r"^https?://[^\s\"'<>]+$")
_NON_SLUG = re.compile(r"[^a-z0-9]+")


def unescape_hn(s: str) -> str:
    """Undo HN's HTML entity escaping (for example ``&#x2F;`` to ``/``)."""
    return html.unescape(s)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_TAGS:
            self.skip_depth += 1
        elif tag in BLOCK_TAGS and not self.skip_depth:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif tag in BLOCK_TAGS and not self.skip_depth:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)


def html_to_text(markup: str) -> str:
    """Visible text of an HTML fragment or page, whitespace collapsed.

    Skips script, style, navigation and similar blocks. Falls back to tag stripping if
    the parser chokes on hostile markup.
    """
    if not markup:
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(markup)
        parser.close()
        raw = "".join(parser.parts)
    except Exception:  # noqa: BLE001 - HTMLParser can raise on pathological input
        raw = html.unescape(_TAG.sub(" ", markup))
    return _WS.sub(" ", raw).strip()


def truncate(s: str, limit: int) -> str:
    """Cut to ``limit`` characters, adding ``...`` when anything was removed."""
    if len(s) <= limit:
        return s
    return s[:limit].rstrip() + "..."


def normalise_url(url: str) -> str:
    """Canonical key for a URL: no scheme, ``www.``, query, fragment or trailing slash.

    Mirrors ``sql.NORM`` exactly; ``tests/test_sql.py`` checks the two agree.
    """
    u = re.sub(r"^https?://", "", url)
    u = re.sub(r"^www\.", "", u)
    u = re.sub(r"[#?].*$", "", u)
    u = re.sub(r"/+$", "", u)
    return u.lower()


def host_of(nurl: str) -> str:
    """Host part of a normalised URL."""
    m = re.match(r"^([^/]+)", nurl)
    return m.group(1) if m else ""


def slugify(s: str, maxlen: int = 80) -> str:
    """Lower-case ASCII slug: letters, digits and single hyphens."""
    slug = _NON_SLUG.sub("-", s.lower()).strip("-")
    return slug[:maxlen].strip("-")


def is_http_url(url: str) -> bool:
    """True for an absolute http or https URL with no whitespace or quote characters."""
    return bool(_HTTP_URL.match(url))


JUNK_TITLES = ("one moment please", "just a moment", "attention required", "access denied",
               "403 forbidden", "client challenge", "are you a robot", "captcha",
               "page not found", "404", "untitled", "home", "index")
CHALLENGE_PHRASES = ("enable javascript and cookies", "checking your browser",
                     "verify you are human", "please turn javascript on",
                     "performing a security check", "ray id")
_PUNCT = re.compile(r"[^a-z0-9 ]+")


def is_junk_title(title: str) -> bool:
    """True for bot-challenge, error and placeholder page titles."""
    t = " ".join(_PUNCT.sub(" ", title.lower()).split())
    return len(t) < 3 or any(t == j or t.startswith(j + " ") for j in JUNK_TITLES)


def is_challenge_page(title: str | None, snippet: str | None) -> bool:
    """True when the fetched page is a bot wall or placeholder rather than the resource."""
    if title and is_junk_title(title):
        return True
    s = (snippet or "").lower()
    return any(p in s for p in CHALLENGE_PHRASES)
