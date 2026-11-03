"""SQL fragments shared by the DuckDB stages.

Each fragment is a format string; pass the column expression as the named argument.
"""

from __future__ import annotations

from hnlearn import config

# HN escapes entities in comment text; undo the common ones so hrefs parse
UNESC = (
    "replace(replace(replace(replace(replace(replace(replace(replace(replace({h},"
    "'&#x2F;','/'),'&#38;','&'),'&amp;','&'),'&#x27;',''''),'&quot;','\"'),"
    "'&#62;','>'),'&#60;','<'),'&gt;','>'),'&lt;','<')"
)
# canonical URL key; keep in step with text.normalise_url
NORM = (
    "lower(regexp_replace(regexp_replace(regexp_replace(regexp_replace({u},'^https?://',''),"
    "'^www\\.',''),'[#?].*$',''),'/+$',''))"
)
HOST = "regexp_extract({n},'^([^/]+)',1)"
# HTML tags to spaces, whitespace collapsed
STRIP = "regexp_replace(regexp_replace({t},'<[^>]+>',' ','g'),'\\s+',' ','g')"
# hrefs inside a comment: unnest(regexp_extract_all(text, HREF, 1))
HREF = "'href=\"([^\"]+)\"'"

REC_REGEX = (
    r"(?i)(highly recommend|strongly recommend|i recommend|i'd recommend|i would recommend|"
    r"can't recommend .{0,20}enough|"
    r"great (resource|intro|introduction|tutorial|book|course|explanation|primer|starting point)|"
    r"excellent (resource|intro|introduction|tutorial|book|course|explanation|primer)|"
    r"best (intro|introduction|tutorial|resource|explanation|book|course|primer)|"
    r"worth (reading|a read|your time|checking out)|must[- ]read|start with|"
    r"good (place to start|starting point|intro|introduction|resource|tutorial)|"
    r"learn(ed|t)? (a lot|so much|a ton) from|taught me|changed (how|the way) i|"
    r"the (canonical|definitive|classic)|if you want to (learn|understand))"
)


def literal(s: str) -> str:
    """Quote a Python string as a SQL string literal."""
    return "'" + s.replace("'", "''") + "'"


def noise_hosts_sql() -> str:
    """``(host, host, ...)`` list of exact noise hosts."""
    return "(" + ", ".join(literal(h) for h in config.NOISE_HOSTS) + ")"


def noise_filter(host_expr: str) -> str:
    """Boolean SQL: true when ``host_expr`` is not a noise host."""
    suffixes = " OR ".join(f"{host_expr} LIKE {literal('%' + s)}"
                           for s in config.NOISE_HOST_SUFFIXES)
    return f"({host_expr} NOT IN {noise_hosts_sql()} AND NOT ({suffixes}))"
