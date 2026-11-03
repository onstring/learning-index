from hnlearn import text


def test_unescape_hn_entities():
    escaped = "https:&#x2F;&#x2F;a.com&#x2F;x?a=1&amp;b=2"
    assert text.unescape_hn(escaped) == "https://a.com/x?a=1&b=2"
    assert text.unescape_hn("it&#x27;s &quot;ok&quot; &gt; &lt;") == "it's \"ok\" > <"


def test_html_to_text_strips_tags_and_collapses_whitespace():
    html = "<p>Hello <i>world</i>.</p><p>Second   line</p>"
    assert text.html_to_text(html) == "Hello world. Second line"


def test_html_to_text_skips_script_style_and_chrome():
    html = ("<html><head><title>T</title><style>.a{}</style><script>var x=1;</script></head>"
            "<body><nav>Menu</nav><header>Top</header><main>Body text</main>"
            "<footer>Foot</footer><noscript>no js</noscript></body></html>")
    assert text.html_to_text(html) == "Body text"


def test_html_to_text_handles_broken_markup():
    assert text.html_to_text("<div><p>unclosed <b>bold") == "unclosed bold"
    assert text.html_to_text("") == ""


def test_truncate():
    assert text.truncate("short", 10) == "short"
    assert text.truncate("a" * 20, 10) == "a" * 10 + "..."
    assert len(text.truncate("word " * 50, 23)) <= 26


def test_normalise_url():
    assert text.normalise_url("https://www.Example.com/Path/?q=1#frag") == "example.com/path"
    assert text.normalise_url("http://example.com///") == "example.com"
    assert text.normalise_url("example.com/a/") == "example.com/a"
    assert text.normalise_url("") == ""


def test_host_of():
    assert text.host_of("example.com/a/b") == "example.com"
    assert text.host_of("example.com") == "example.com"
    assert text.host_of("") == ""


def test_slugify():
    assert text.slugify("Teach Yourself CS!") == "teach-yourself-cs"
    assert text.slugify("a/b_c.d") == "a-b-c-d"
    assert text.slugify("  --x--  ") == "x"
    assert len(text.slugify("y" * 200, maxlen=20)) == 20


def test_is_http_url():
    assert text.is_http_url("https://a.com")
    assert text.is_http_url("http://a.com/x")
    assert not text.is_http_url("javascript:alert(1)")
    assert not text.is_http_url("ftp://a.com")
    assert not text.is_http_url("https://a.com/x y")
