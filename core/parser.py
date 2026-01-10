import re
from dataclasses import dataclass
from typing import List, Optional

url_template = re.compile(r"((https?|ftp|file|ii)://?[-A-Za-z0-9+&@#/%?=~_|!:,.;]+[-A-Za-z0-9+&@#/%=~_|])")
# noinspection RegExpRedundantEscape
ps_template = re.compile(r"(^\s*)(PS|P.S|ps|ЗЫ|З.Ы|\/\/|#)")
# noinspection RegExpRedundantEscape
quote_template = re.compile(r"^\s*[a-zA-Zа-яА-Я0-9_\-.\(\)]{0,20}>{1,20}")
origin_template = re.compile(r"^\s*\+\+\+")


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
    w = 0
    y = 0
    for token in tokens:
        if token.line_num > line_num:
            y += 1
            w = 0
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
        if w + len(value) <= width:
            w += len(value)
            token.render.append(value)
            continue  # tokens
        if token.type == "CODE":
            # do not split leading spaces
            line = ""
            chunk = value[0:width - w]
            value = value[width - w:]
            while chunk:
                line += chunk
                token.render.append(line)
                line = ""
                w = 0
                chunk = value[0:width]
                value = value[width:]
            y += len(token.render) - 1
            continue  # tokens

        # to wide, split by words
        words = value.split(" ")
        space = ""
        line = ""
        for word in words:
            word = space + word
            space = " "
            if w + len(word) <= width:
                line += word
                w += len(word)
                continue  # words
            # new line
            if w:
                token.render.append(line)
            line = ""
            w = 0
            if word.startswith(" "):
                word = word[1:]
            if len(word) <= width:
                line += word
                w += len(word)
                space = " "
                continue  # words

            # len(word) > width
            chunk = word[0:width]
            word = word[width:]
            while chunk:
                line += chunk
                token.render.append(line)
                line = ""
                w = 0
                chunk = word[0:width]
                word = word[width:]
        if line:
            token.render.append(line)
        y += len(token.render) - 1
    if height and y + 1 > height:
        # scrollable detected, reserve scrollbar width
        return prerender(tokens, width=width - 1, height=None)
    return y + 1  #


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
