import duckdb
import pytest

from hnlearn import sql, text

SAMPLES = [
    "https://www.Example.com/Path/?q=1#frag",
    "http://example.com///",
    "https:&#x2F;&#x2F;a.com&#x2F;x?a=1&amp;b=2",
    "https://teachyourselfcs.com/",
    "https://a.com/x&amp;lt;y",  # must not double-decode to "<"
    "",
]


@pytest.mark.parametrize("raw", SAMPLES)
def test_sql_normalisation_matches_python(raw):
    con = duckdb.connect()
    expr = sql.NORM.format(u=sql.UNESC.format(h="?"))
    got = con.execute(f"SELECT {expr}", [raw]).fetchone()[0]
    assert got == text.normalise_url(text.unescape_hn(raw))


def test_sql_host_matches_python():
    con = duckdb.connect()
    got = con.execute(f"SELECT {sql.HOST.format(n='?')}", ["example.com/a/b"]).fetchone()[0]
    assert got == text.host_of("example.com/a/b") == "example.com"


def test_unescape_does_not_double_decode():
    con = duckdb.connect()
    got = con.execute(f"SELECT {sql.UNESC.format(h='?')}", ["x&amp;lt;y &#38;amp; z"]).fetchone()[0]
    assert got == "x&lt;y &amp; z" == text.unescape_hn("x&amp;lt;y &#38;amp; z")


def test_recommendation_regex_matches_and_rejects():
    con = duckdb.connect()
    lit = sql.literal(sql.REC_REGEX)
    hits = ["I highly recommend this", "it's a great resource for beginners", "Worth reading",
            "can't recommend it enough", "if you want to learn Rust, read this"]
    misses = ["I bought this yesterday", "the weather is nice", "recommendation engine"]
    for s in hits:
        assert con.execute(f"SELECT regexp_matches(?, {lit})", [s]).fetchone()[0], s
    for s in misses:
        assert not con.execute(f"SELECT regexp_matches(?, {lit})", [s]).fetchone()[0], s


def test_literal_doubles_single_quotes():
    assert sql.literal("it's") == "'it''s'"


def test_noise_hosts_sql_is_a_valid_in_list():
    con = duckdb.connect()
    assert con.execute(f"SELECT 'youtube.com' IN {sql.noise_hosts_sql()}").fetchone()[0]
    assert not con.execute(f"SELECT 'teachyourselfcs.com' IN {sql.noise_hosts_sql()}").fetchone()[0]
