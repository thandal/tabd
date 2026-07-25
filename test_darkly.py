"""Regression tests for the parts of Darkly that silently mangle content.

Run with:  python_env/bin/python test_darkly.py
(also works under pytest if you have it)
"""
from darkly_addon import MarkdownStreamParser, dom_to_condensed

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
    assert '<a href="https://ex.com/a">x</a>' in out, out
    assert '<img src="https://ex.com/i.png"' in out, out


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
