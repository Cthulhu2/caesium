from core import parser
from core.parser import Token

BASE_TOKENS = """Test
== Header
 * List item
 Quoter2>> Quote2
 Quoter1> Quote1
Regular text
http://url
====
Code
====
----
PS: PostScript
+++ Origin
"""


def test_base_tokens():
    tokens = parser.tokenize(BASE_TOKENS.splitlines())
    assert tokens[0] == Token("TEXT", "Test", 0)
    assert tokens[1] == Token("HEADER", "== Header", 1)
    assert tokens[2] == Token("TEXT", " * List item", 2)
    assert tokens[3] == Token("QUOTE2", " Quoter2>> Quote2", 3)
    assert tokens[4] == Token("QUOTE1", " Quoter1> Quote1", 4)
    assert tokens[5] == Token("TEXT", "Regular text", 5)
    assert tokens[6] == Token("URL", "http://url", 6)
    assert tokens[7] == Token("CODE", "====", 7)
    assert tokens[8] == Token("CODE", "Code", 8)
    assert tokens[9] == Token("CODE", "====", 9)
    assert tokens[10] == Token("HR", "----", 10)
    assert tokens[11] == Token("COMMENT", "PS: PostScript", 11)
    assert tokens[12] == Token("ORIGIN", "+++ Origin", 12)
    assert len(tokens) == 13


EMPTY_LINES = """
Regular text

with empty lines
====
code

with empty lines
+++ Origin in Code
====

====
Unclosed code

"""


def test_empty_lines():
    tokens = parser.tokenize(EMPTY_LINES.splitlines())
    assert tokens[0] == Token("TEXT", "", 0)
    assert tokens[1] == Token("TEXT", "Regular text", 1)
    assert tokens[2] == Token("TEXT", "", 2)
    assert tokens[3] == Token("TEXT", "with empty lines", 3)
    assert tokens[4] == Token("CODE", "====", 4)
    assert tokens[5] == Token("CODE", "code", 5)
    assert tokens[6] == Token("CODE", "", 6)
    assert tokens[7] == Token("CODE", "with empty lines", 7)
    assert tokens[8] == Token("CODE", "+++ Origin in Code", 8)
    assert tokens[9] == Token("CODE", "====", 9)
    assert tokens[10] == Token("TEXT", "", 10)
    assert tokens[11] == Token("TEXT", "====", 11)
    assert tokens[12] == Token("TEXT", "Unclosed code", 12)
    assert tokens[13] == Token("TEXT", "", 13)
    assert len(tokens) == 14


URL_INLINE = """Regular text w http://inline-url in the middle.
== Header w http://header-inline-url in the middle.
 Quoter2>> Quote2 w http://quote2-inline-url in the middle.
 Quoter1> Quote1 w http://quote1-inline-url in the middle.
====
Code w http://code-inline-url in the middle.
====
----
PS: PostScript w http://ps-inline-url in the middle.
+++ Origin w http://origin-inline-url in the middle.
"""


def test_url_inline():
    tokens = parser.tokenize(URL_INLINE.splitlines())
    assert tokens[0] == Token("TEXT", "Regular text w ", 0)
    assert tokens[1] == Token("URL", "http://inline-url", 0)
    assert tokens[2] == Token("TEXT", " in the middle.", 0)
    assert tokens[3] == Token("HEADER", "== Header w ", 1)
    assert tokens[4] == Token("URL", "http://header-inline-url", 1)
    assert tokens[5] == Token("HEADER", " in the middle.", 1)
    assert tokens[6] == Token("QUOTE2", " Quoter2>> Quote2 w ", 2)
    assert tokens[7] == Token("URL", "http://quote2-inline-url", 2)
    assert tokens[8] == Token("QUOTE2", " in the middle.", 2)
    assert tokens[9] == Token("QUOTE1", " Quoter1> Quote1 w ", 3)
    assert tokens[10] == Token("URL", "http://quote1-inline-url", 3)
    assert tokens[11] == Token("QUOTE1", " in the middle.", 3)
    assert tokens[12] == Token("CODE", "====", 4)
    assert tokens[13] == Token("CODE", "Code w ", 5)
    assert tokens[14] == Token("URL", "http://code-inline-url", 5)
    assert tokens[15] == Token("CODE", " in the middle.", 5)
    assert tokens[16] == Token("CODE", "====", 6)
    assert tokens[17] == Token("HR", "----", 7)
    assert tokens[18] == Token("COMMENT", "PS: PostScript w ", 8)
    assert tokens[19] == Token("URL", "http://ps-inline-url", 8)
    assert tokens[20] == Token("COMMENT", " in the middle.", 8)
    assert tokens[21] == Token("ORIGIN", "+++ Origin w ", 9)
    assert tokens[22] == Token("URL", "http://origin-inline-url", 9)
    assert tokens[23] == Token("ORIGIN", " in the middle.", 9)
    assert len(tokens) == 24


SOFT_WRAP = """==     long-long-long-long-header
New line with many words.

Long http://url-with-many-words/and?query.
----
"""


def test_soft_wrap():
    tokens = parser.tokenize(SOFT_WRAP.splitlines())
    assert tokens[0] == Token("HEADER", "==     long-long-long-long-header", 0)
    assert tokens[1] == Token("TEXT", "New line with many words.", 1)
    assert tokens[2] == Token("TEXT", "", 2)
    assert tokens[3] == Token("TEXT", "Long ", 3)
    assert tokens[4] == Token("URL", "http://url-with-many-words/and"
                                     "?query", 3)
    assert tokens[5] == Token("TEXT", ".", 3)
    assert tokens[6] == Token("HR", "----", 4)

    assert parser.prerender(tokens, width=10) == 14
    assert tokens[0].render == ["==     lon",
                                "g-long-lon",
                                "g-long-hea",
                                "der"]
    assert tokens[1].render == ["New line",
                                "with many",
                                "words."]
    assert tokens[2].render == [""]
    assert tokens[3].render == ["Long "]
    # @formatter:off
    assert tokens[4].render == [     "http:",  # noqa
                                "//url-with",
                                "-many-word",
                                "s/and?quer",
                                "y"]
    # @formatter:on
    assert tokens[5].render == ["."]
    assert tokens[6].render == ["──────────"]


SOFT_WRAP_TRAILING = """http://url and text in one line.
http://url long-word in other line
"""


def test_soft_wrap_trailing():
    tokens = parser.tokenize(SOFT_WRAP_TRAILING.splitlines())
    assert tokens[0] == Token("URL", "http://url", 0)
    assert tokens[1] == Token("TEXT", " and text in one line.", 0)
    assert tokens[2] == Token("URL", "http://url", 1)
    assert tokens[3] == Token("TEXT", " long-word in other line", 1)
    #
    assert parser.prerender(tokens, width=14) == 6
    # @formatter:off
    assert tokens[0].render == ["http://url"]
    assert tokens[1].render == [          " and",  # noqa
                                "text in one",
                                "line."]
    assert tokens[2].render == ["http://url"]
    assert tokens[3].render == [          "",  # noqa
                                "long-word in",
                                "other line"]
    # @formatter:on


def test_find_visible_token():
    tokens = parser.tokenize(SOFT_WRAP.splitlines())
    parser.prerender(tokens, width=10)
    #
    y, offset = parser.find_visible_token(tokens, 0)
    assert (y, offset) == (0, 0)
    #
    y, offset = parser.find_visible_token(tokens, 1)
    assert (y, offset) == (0, 1)
    #
    y, offset = parser.find_visible_token(tokens, 3)
    assert (y, offset) == (0, 3)
    assert tokens[y].render[offset] == "der"
    #
    y, offset = parser.find_visible_token(tokens, 4)
    assert (y, offset) == (1, 0)
    assert tokens[y].render[offset] == "New line"
    #
    y, offset = parser.find_visible_token(tokens, 9)
    assert (y, offset) == (4, 1)
    assert tokens[y].render[offset] == "//url-with"


def test_scrollable_size():
    tokens = parser.tokenize([""])
    assert parser.prerender(tokens, width=10) == 1

    tokens = parser.tokenize(["", ""])
    assert parser.prerender(tokens, width=10) == 2

    tokens = parser.tokenize(SOFT_WRAP.splitlines())
    assert parser.prerender(tokens, width=10) == 14

    tokens = parser.tokenize(SOFT_WRAP_TRAILING.splitlines())
    assert parser.prerender(tokens, width=14) == 6


def test_scrollable_last_token():
    tokens = parser.tokenize(["1234 5678 9012 3456"])
    parser.prerender(tokens, width=4, height=2)
    #
    line_num = 0
    body = ""
    for t in tokens:
        if t.line_num > line_num:
            body += "\n"
            line_num = t.line_num
        body += "\n".join(t.render)
    #
    b_width = max([len(line) for line in body.split("\n")])
    assert b_width == 3


def test_render_tabs():
    tokens = parser.tokenize([
        "====",
        "\tpublic {",
        "\t\tprint;",
        "\t}",
        "===="
    ])
    b_height = parser.prerender(tokens, width=10, height=1)
    assert tokens[0].render == ["===="]
    assert tokens[1].render == ["    publi",
                                "c {"]
    assert tokens[2].render == ["        p",
                                "rint;"]
    assert tokens[3].render == ["    }"]
    assert tokens[4].render == ["===="]
    assert b_height == 7


def test_quote_url():
    tokens = parser.tokenize([">http://in-quote"])
    b_height = parser.prerender(tokens, width=20)
    assert tokens[0].render == [" >"]
    assert tokens[1].render == ["http://in-quote"]
    assert b_height == 1


class ScrMock:
    def __init__(self, h, w):
        self.height = h
        self.width = w

    def addstr(self, y, x, line):
        assert y < self.height
        assert x + len(line) <= self.width


# TODO: Make render_token testable
def _render_token(scr, token: parser.Token, y, x, offset):
    for i, line in enumerate(token.render[offset:]):
        scr.addstr(y + i, x, line)

        if len(token.render) > 1 and i + offset < len(token.render) - 1:
            x = 0  # new line in multiline token -- carriage return
        else:
            x += len(line)  # last/single line -- move caret in line
        if y + i + 1 >= 30 - 1:
            return y + i, x
    return y + (len(token.render) - 1) - offset, x


def test_render_token():
    tokens = parser.tokenize([
        "aaaaaa> aaa-aa aaaaa aaa aaaaaaaaaa https://aaaa.aaaaaaaa.aa/. ",
        "aaaaaa> aaaaa aaaaaaaa aaaa https://aaaaaa.com/aaaaaaaaaa/aaaaaaaaaaaa-aaa",
        "",
    ])
    b_height = parser.prerender(tokens, width=62, height=30)
    i = 5
    x = 0
    scr = ScrMock(30, 62)
    line_num = 0
    for token in tokens:
        if token.line_num > line_num:
            line_num = token.line_num
            i += 1
            x = 0
        if i >= 30 - 1:
            break
        i, x = _render_token(scr=scr, token=token, y=i, x=x, offset=0)
