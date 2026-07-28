"""Regression tests for the parts of Darkly that silently mangle content.

Run with:  python_env/bin/python test_darkly.py
(also works under pytest if you have it)
"""
from unittest.mock import patch

from bs4 import BeautifulSoup

from darkly_addon import MarkdownStreamParser, dom_to_condensed
from darkly_server import BlockedURL, _check_url_allowed, app

MAPPING = {1: {"type": "a", "href": "/a"},
           2: {"type": "img", "src": "/i.png", "alt": "pic"}}


def render(md, chunk_size=10**9):
    p = MarkdownStreamParser(dict(MAPPING), "https://ex.com", "")
    out = "".join(p.process_chunk(md[i:i + chunk_size])
                  for i in range(0, len(md), chunk_size))
    return out + p.finish()


# --- dom_to_condensed -------------------------------------------------------

def test_nested_blocks_keep_their_boundaries():
    """Regression: clean_text used to collapse \\n, flattening whole pages to one line."""
    html = ("<body><div><div><article>"
            "<h1>Title</h1><p>One.</p><p>Two.</p>"
            "<ul><li>a</li><li>b</li></ul>"
            "</article></div></div></body>")
    condensed, _ = dom_to_condensed(html)
    assert condensed.split("\n") == ["Title", "One.", "Two.", "a", "b"], condensed


def test_source_line_wrapping_does_not_create_blocks():
    html = "<body><p>wrapped\n   across\n   lines</p></body>"
    condensed, _ = dom_to_condensed(html)
    assert condensed == "wrapped across lines", repr(condensed)


def test_link_text_stays_on_one_line():
    html = "<body><p>see <a href='/x'><span>multi</span>\n<span>word</span></a></p></body>"
    condensed, mapping = dom_to_condensed(html)
    assert "\n" not in condensed, repr(condensed)
    assert mapping[1]["href"] == "/x"


def test_no_blank_or_whitespace_only_lines():
    html = "<body><article><p>a</p></article>\n\n  \n<nav><p>b</p></nav></body>"
    condensed, _ = dom_to_condensed(html)
    assert all(line.strip() for line in condensed.split("\n")), repr(condensed)


# --- MarkdownStreamParser ---------------------------------------------------

def test_loose_list_is_one_list():
    """Regression: splitting on \\n\\n produced one <ul> per item."""
    out = render("- one\n\n- two\n\n- three\n")
    assert out.count("<ul>") == 1, out


def test_table_survives_blank_line_split():
    out = render("| a | b |\n|---|---|\n| 1 | 2 |\n")
    assert "<table>" in out, out


def test_fenced_code_with_blank_lines():
    out = render("```python\ndef f():\n\n    return 1\n```\n")
    assert "<code" in out and "return 1" in out, out
    assert "<p>```" not in out, out


def test_blockquote_spanning_blank_line():
    out = render("> one\n>\n> two\n")
    assert out.count("<blockquote>") == 1, out


def test_document_wrapping_fence_is_stripped():
    out = render("```markdown\n# Title\n\nBody.\n```", chunk_size=4)
    assert out.startswith("<h1>Title</h1>"), out
    assert "```" not in out, out


def test_ids_are_restored():
    out = render("Text [x][1] and ![pic][2].\n")
    assert 'href="https://ex.com/a"' in out and ">x</a>" in out, out
    assert '<img src="https://ex.com/i.png"' in out, out


def test_image_syntax_on_link_id_becomes_link():
    # A thumbnail inside an anchor tempts the model into ![alt][id] with the
    # anchor's id. Rendering that as <img src="<article page>"> makes the
    # browser fetch one HTML page per thumbnail (the /proxy subresource guard
    # then 415s each one). It must render as a link, or nothing without alt.
    mapping = {1: {'type': 'a', 'href': 'https://ex.com/article'}}
    parser = MarkdownStreamParser(mapping, "https://ex.com", "/proxy?url=")
    out = parser.process_chunk("![Story][1]\n") + parser.finish()
    assert "<img" not in out, out
    assert 'href="/proxy?url=https%3A%2F%2Fex.com%2Farticle"' in out, out
    assert ">Story</a>" in out, out
    parser = MarkdownStreamParser(mapping, "https://ex.com", "/proxy?url=")
    out = parser.process_chunk("![][1]\n") + parser.finish()
    assert "<img" not in out and "<a" not in out, out


def test_unknown_id_is_left_alone():
    out = render("Text [x][99].\n")
    assert "[x][99]" in out, out


def test_output_is_independent_of_chunk_boundaries():
    doc = ("# H\n\nPara with [x][1].\n\n- one\n\n- two\n\n"
           "| a | b |\n|---|---|\n| 1 | 2 |\n\n> q\n>\n> q2\n\n"
           "```py\nx = 1\n\ny = 2\n```\n\nEnd.\n")
    reference = render(doc)
    for size in (1, 2, 3, 5, 7, 13, 64, 512):
        assert render(doc, size) == reference, f"differs at chunk size {size}"


def test_executable_html_is_removed():
    out = render('<script>alert(1)</script><img src="x" onerror="alert(2)">\n')
    assert "script" not in out.lower(), out
    assert "onerror" not in out.lower(), out


def test_unsafe_urls_are_removed():
    out = render("[click](javascript:alert(1))\n")
    assert "javascript:" not in out.lower(), out


def test_mapped_attributes_cannot_break_out():
    mapping = {1: {"type": "a", "href": '/x" onmouseover="alert(1)'}}
    parser = MarkdownStreamParser(mapping, "https://ex.com", "")
    out = parser.process_chunk("[click][1]\n") + parser.finish()
    link = BeautifulSoup(out, "html.parser").find("a")
    assert "onmouseover" not in link.attrs, out


def test_cgnat_is_blocked():
    try:
        _check_url_allowed("http://100.100.100.200/")
    except BlockedURL:
        return
    raise AssertionError("CGNAT address was allowed")


def test_prefetch_never_reaches_the_origin():
    with patch("darkly_server.fetch_page",
               side_effect=AssertionError("fetched during a prefetch")):
        with app.test_client() as client:
            r = client.get("/proxy?url=https://ex.com",
                           headers={"Sec-Purpose": "prefetch"})
    assert r.status_code == 503, r.status_code


def test_html_subresource_request_is_not_simplified():
    class Page:
        headers = {"Content-Type": "text/html"}
        content = b"<p>x</p>"
        text = "<p>x</p>"

    async def fake_simplify(*_args):
        yield "<p>simplified</p>"

    with patch("darkly_server.fetch_page", return_value=(Page(), "https://ex.com")):
        with patch("darkly_server.simplify_html_stream", fake_simplify):
            with app.test_client() as client:
                image = client.get("/proxy?url=https://ex.com",
                                   headers={"Sec-Fetch-Dest": "image"})
                navigation = client.get("/proxy?url=https://ex.com",
                                        headers={"Sec-Fetch-Dest": "iframe"})
    assert image.status_code == 415, image.status_code
    assert navigation.status_code == 200, navigation.status_code
    assert navigation.get_data(as_text=True) == "<p>simplified</p>"


def test_model_added_links_stay_direct():
    # Links the model injects (e.g. fact-check searches) are not proxied —
    # search engines bot-block the server-side fetch — and open in a new tab
    # since the result iframe cannot navigate to sites that refuse framing.
    doc = "[check](https://www.google.com/search?q=x)\n"
    parser = MarkdownStreamParser({}, "https://ex.com", "/proxy?url=")
    out = parser.process_chunk(doc) + parser.finish()
    assert 'href="https://www.google.com/search?q=x"' in out, out
    assert 'target="_blank"' in out, out
    # Without a proxy prefix (the mitmproxy path) they stay direct, same tab.
    parser = MarkdownStreamParser({}, "https://ex.com", "")
    out = parser.process_chunk(doc) + parser.finish()
    assert 'href="https://www.google.com/search?q=x"' in out, out
    assert 'target=' not in out, out


def test_preexisting_links_are_still_proxied():
    mapping = {1: {'type': 'a', 'href': 'https://ex.com/page'}}
    doc = "[go][1]\n"
    parser = MarkdownStreamParser(mapping, "https://ex.com", "/proxy?url=")
    out = parser.process_chunk(doc) + parser.finish()
    assert 'href="/proxy?url=https%3A%2F%2Fex.com%2Fpage"' in out, out
    assert 'target=' not in out, out


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    raise SystemExit(1 if failures else 0)
