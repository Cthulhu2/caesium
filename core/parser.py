import re
from dataclasses import dataclass
from typing import List, Optional

url_template = re.compile(r"((https?|ftp|file|ii)://?"
                          r"[-A-Za-zА-Яа-яЁё0-9+&@#/%?=~_|!:,.;()]+"
                          r"[-A-Za-zА-Яа-яЁё0-9+&@#/%=~_|()])")
# noinspection RegExpRedundantEscape
ps_template = re.compile(r"(^\s*)(PS|P\.S|ps|ЗЫ|З\.Ы|\/\/|#)")
# noinspection RegExpRedundantEscape
quote_template = re.compile(r"^\s*[a-zA-Zа-яА-Я0-9_\-.\(\)]{0,20}>{1,20}")
origin_template = re.compile(r"^\s*\+\+\+")
echo_template = re.compile(r"^[a-z0-9_!.-]{1,60}\.[a-z0-9_!.-]{1,60}$")


@dataclass
class Token:
    type: str  # HEADER, URL, TEXT, QUOTE1, QUOTE2, HR, ORIGIN
    value: str
    line_num: int  # номер строки (начиная с 0)
    render: List[str] = None  # строки с мягкими переносами


def tokenize(lines: List[str], start_line=0) -> List[Token]:
    tokens = []
    line_num = 0
    while line_num < len(lines):
        line = lines[line_num]
        #
        if line.startswith('== '):
            tokens.extend(_tokenize_inline(
                text=line[3:],
                line_num=line_num + start_line,
                token=Token("HEADER", "== ", line_num + start_line)))
            line_num += 1
            continue  #
        #
        comment = ps_template.search(line)
        if comment:
            tokens.extend(_tokenize_inline(
                text=line[comment.end():],
                line_num=line_num + start_line,
                token=Token("COMMENT", line[0:comment.end()], line_num + start_line)
            ))
            line_num += 1
            continue  #
        #
        quote = quote_template.match(line)
        if quote:
            count = line[0:quote.span()[1]].count(">")
            kind = "QUOTE" + str(((count + 1) % 2) + 1)
            tokens.extend(_tokenize_inline(
                text=line[quote.end():],
                line_num=line_num + start_line,
                token=Token(kind, line[0:quote.end()], line_num + start_line)
            ))
            line_num += 1
            continue  #
        #
        origin = origin_template.search(line)
        if origin:
            tokens.extend(_tokenize_inline(
                text=line[origin.end():],
                line_num=line_num + start_line,
                token=Token("ORIGIN", line[0:origin.end()], line_num + start_line)
            ))
            line_num += 1
            continue  #
        #
        if line.rstrip() == "----":
            tokens.append(Token("HR", line, line_num + start_line))
            line_num += 1
            continue  #
        #
        if line.rstrip() == "====":
            next_lines = lines[line_num + 1:]
            if any(filter(lambda s: s.rstrip() == "====", next_lines)):
                tokens.append(Token("CODE", line, line_num + start_line))
                line_num += 1
                for nline in next_lines:
                    tokens.extend(_tokenize_inline(
                        nline,
                        line_num,
                        Token("CODE", "", line_num + start_line)))
                    line_num += 1
                    if nline.rstrip() == "====":
                        break  #
                continue  #
        #
        tokens.extend(_tokenize_inline(
            line,
            line_num + start_line,
            token=Token("TEXT", "", line_num + start_line)))
        line_num += 1

    return tokens


def _tokenize_inline(text: str, line_num: int, token: Token) -> List[Token]:
    tokens = []
    pos = 0
    while pos < len(text):
        match = url_template.search(text, pos)
        if match and match.start() == pos:
            url = match.group()
            if token.value:
                tokens.append(token)
                token = Token(token.type, "", line_num)
            tokens.append(Token("URL", url, line_num))
            pos = match.end()
        else:
            url_start = match.start() if match else len(text)
            raw_text = text[pos:url_start]
            token.value += raw_text
            tokens.append(token)
            pos = url_start
            token = Token(token.type, "", line_num)
    if not text:
        tokens.append(token)
    return tokens


def prerender(tokens, width, height=None):
    # type: (List[Token], int, Optional[int]) -> int
    """:return: body height lines count"""
    if not tokens:
        return 1  #
    line_num = tokens[0].line_num
    x = 0
    y = 0
    for token in tokens:
        if token.line_num > line_num:
            y += 1
            x = 0
            line_num = token.line_num
        if token.render is None:
            token.render = []
        else:
            token.render.clear()
        if height and y + 1 > height:
            # early scrollable detected, reserve scrollbar width
            return prerender(tokens, width=width - 1, height=None)
        # pre-process
        value = token.value
        if value and token.type in ("QUOTE1", "QUOTE2") and value[0] != " ":
            value = " " + value
        if token.type == "HR":
            value = "─" * width
        value = value.replace("\t", "    ")

        # render token
        if x + len(value) <= width:
            x += len(value)
            token.render.append(value)
            continue  # tokens
        if token.type == "CODE":
            # do not split leading spaces
            x = render_chunks(token, "", x, width, value)
            y += len(token.render) - 1
            continue  # tokens

        # too wide, split by words
        words = value.split(" ")
        space = ""
        line = ""
        empty_new_line = False
        for word in words:
            empty_new_line = False
            word = space + word
            space = " "
            # insert word
            if x + len(word) <= width:
                line += word
                x += len(word)
                continue  # words
            # insert chunks
            if x + 1 < width < len(word):
                x = render_chunks(token, line, x, width, word)
                line = token.render.pop(len(token.render) - 1)
                continue  # words
            # new line
            if x:
                token.render.append(line)
            if word.startswith(" "):
                word = word[1:]
            if len(word) <= width:
                line = word
                x = len(word)
                space = " "
                empty_new_line = (x == 0)
                continue  # words

            # len(word) > width
            x = render_chunks(token, "", 0, width, word)
            line = token.render.pop(len(token.render) - 1)
        if line or empty_new_line:
            token.render.append(line)
        y += len(token.render) - 1
    if height and y + 1 > height:
        # scrollable detected, reserve scrollbar width
        return prerender(tokens, width=width - 1, height=None)
    return y + 1  #


def render_chunks(token, line, x, width, word):
    chunk = word[0:width - x]
    word = word[width - x:]
    while chunk:
        token.render.append(line + chunk)
        x = len(line + chunk)
        line = ""
        chunk = word[0:width]
        word = word[width:]
    return x


def find_visible_token(tokens, scroll):
    # type: (List[Token], int) -> (int, int)
    """
    :return: Token num, offset in token.render
    """
    y = 0
    line_num = 0
    if scroll < 0:
        scroll = 0
    for i, token in enumerate(tokens):
        if token.line_num > line_num:
            line_num = token.line_num
            y += 1
        height = len(token.render) - 1
        y += height
        if y >= scroll:
            return i, height - (y - scroll)  #
    #
    return len(tokens) - 1, len(tokens[-1].render) - 1


def scrollable_size(tokens):
    # type: (List[Token]) -> int
    y = 0
    line_num = 0
    for token in tokens:
        if token.line_num > line_num:
            line_num = token.line_num
            y += 1
        y += len(token.render) - 1
    return y + 1
