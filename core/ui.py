import curses
from datetime import datetime
from typing import Optional, List

import keys.default as keys
from core import __version__, parser, utils, search, keystroke
from core.config import (
    get_color, TOKEN2UI,
    UI_BORDER, UI_CURSOR, UI_STATUS, UI_SCROLL, UI_TITLES, UI_TEXT
)

LABEL_ANY_KEY = "Нажмите любую клавишу"
LABEL_ESC = "Esc - отмена"
HEIGHT = 0
WIDTH = 0

stdscr = None  # type: Optional[curses.window]
version = "Caesium/%s │" % __version__


def set_term_size():
    global HEIGHT, WIDTH, stdscr
    HEIGHT, WIDTH = stdscr.getmaxyx()


def initialize_curses():
    global stdscr
    stdscr = curses.initscr()
    curses.start_color()
    curses.use_default_colors()
    curses.noecho()
    curses.set_escdelay(50)  # ms
    curses.curs_set(0)
    curses.cbreak()
    stdscr.keypad(True)
    set_term_size()


def terminate_curses():
    curses.curs_set(1)
    if stdscr:
        stdscr.keypad(False)
    curses.echo(True)
    curses.nocbreak()
    curses.endwin()


def get_keystroke():
    stdscr.timeout(-1)
    key = stdscr.getch()
    stdscr.timeout(0)
    ks, key, _ = keystroke.getkeystroke(stdscr, key)
    stdscr.timeout(-1)
    return ks, key, _


def draw_splash(scr, splash):  # type: (curses.window, List[str]) -> None
    scr.clear()
    h, w = scr.getmaxyx()
    x = int((w - len(splash[1])) / 2) - 1
    y = int((h - len(splash)) / 2)
    color = get_color(UI_TEXT)
    for i, line in enumerate(splash):
        scr.addstr(y + i, x, line, color)
    scr.refresh()


def draw_title(scr, y, x, title):
    h, w = scr.getmaxyx()
    x = max(0, x)
    if (x + len(title) + 2) > w:
        title = title[:w - x - 2 - 3] + '...'
    #
    color = get_color(UI_BORDER)
    scr.addstr(y, x, "[", color)
    scr.addstr(y, x + 1 + len(title), "]", color)
    color = get_color(UI_TITLES)
    scr.addstr(y, x + 1, title, color)


def draw_message_box(smsg, wait):
    msg = smsg.split("\n")
    maxlen = max(map(lambda x: len(x), msg))
    if wait:
        maxlen = max(len(LABEL_ANY_KEY), maxlen)
        win = curses.newwin(len(msg) + 4,
                            maxlen + 2,
                            int(HEIGHT / 2 - 2),
                            int(WIDTH / 2 - maxlen / 2 - 2))
    else:
        win = curses.newwin(len(msg) + 2,
                            maxlen + 2,
                            int(HEIGHT / 2 - 2),
                            int(WIDTH / 2 - maxlen / 2 - 2))
    win.bkgd(' ', get_color(UI_TEXT))
    win.attrset(get_color(UI_BORDER))
    win.border()

    color = get_color(UI_TEXT)
    for i, line in enumerate(msg, start=1):
        win.addstr(i, 1, line, color)

    color = get_color(UI_TITLES)
    if wait:
        win.addstr(len(msg) + 2, int((maxlen + 2 - len(LABEL_ANY_KEY)) / 2),
                   LABEL_ANY_KEY, color)
    win.refresh()


def show_message_box(smsg):
    draw_message_box(smsg, True)
    stdscr.getch()
    stdscr.clear()


def draw_scrollbarV(scr, y, x, scroll):
    # type: (curses.window, int, int, ScrollCalc) -> None
    color = get_color(UI_SCROLL)
    for i in range(y, y + scroll.track):
        scr.addstr(i, x, "░", color)
    for i in range(y + scroll.thumb_pos, y + scroll.thumb_pos + scroll.thumb_sz):
        scr.addstr(i, x, "█", color)


def draw_status_bar(scr, text=None):  # type: (curses.window, str) -> None
    h, w = scr.getmaxyx()
    color = get_color(UI_STATUS)
    scr.insstr(h - 1, 0, " " * w, color)
    scr.addstr(h - 1, 1, version, color)
    scr.addstr(h - 1, w - 8, "│ " + datetime.now().strftime("%H:%M"), color)
    if text:
        scr.addstr(h - 1, len(version) + 2, text, color)
    if parser.INLINE_STYLE_ENABLED:
        scr.addstr(h - 1, w - 10, "~", color)


class ScrollCalc:
    content: int  # scrollable content length
    view: int  # scroll view length
    thumb_sz: int  # thumb size
    track: int  # track length
    _pos: int = 0  # scroll position in the scrollable content
    #
    thumb_pos: int  # calculated thumb position on the track
    is_scrollable = False

    def __init__(self, content: int, view: int,
                 pos: int = 0, track: int = None):
        self.content = content
        self.view = view
        self.thumb_sz = max(1, min(self.view, int(self.view * self.view
                                                  / self.content + 0.5)))
        self.track = track or view
        self.is_scrollable = self.content > self.view
        self._pos = max(0, min(self.content - self.view, pos))
        self.calc()

    @property
    def pos(self):
        return self._pos

    @pos.setter
    def pos(self, pos):
        if self._pos == pos:
            return
        self._pos = max(0, min(self.content - self.view, pos))
        self.calc()

    def pos_bottom(self):
        return max(0, min(self.pos + self.view, self.content) - 1)

    def calc(self):
        available_track = self.track - self.thumb_sz
        thumb_pos = 0
        if self.is_scrollable:
            thumb_pos = int((self.pos / (self.content - self.view))
                            * available_track + 0.5)
        self.thumb_pos = max(0, min(available_track, thumb_pos))

    def ensure_visible(self, pos, center=False):
        if pos < self.pos:
            self.pos = pos  # scroll up
            if center:
                self.pos -= self.view // 2
        elif pos >= self.pos + self.view:
            self.pos = pos - self.view + 1  # scroll down
            if center:
                self.pos += self.view // 2


class SelectWindow:
    scroll: ScrollCalc

    def __init__(self, title, items):
        self.title = title
        self.items = items
        self.cursor = 0
        self.win = self.init_win(self.items, self.title)
        self.resized = False

    def init_win(self, items, title, win=None):
        test_width = items + [LABEL_ESC + "[]", title + "[]"]
        w = 0 if not items else max(map(lambda it: len(it), test_width))
        h = min(HEIGHT - 2, len(items))
        w = min(WIDTH - 2, w)
        y = max(0, int(HEIGHT / 2 - h / 2 - 2))
        x = max(0, int(WIDTH / 2 - w / 2 - 2))
        if win:
            win.resize(h + 2, w + 2)
            win.mvwin(y, x)
        else:
            win = curses.newwin(h + 2, w + 2, y, x)
        color = get_color(UI_BORDER)
        lbl_title = title[0:min(w - 4, len(title))]
        lbl_esc = LABEL_ESC[0:min(w - 4, len(LABEL_ESC))]
        win.attrset(color)
        win.border()
        win.addstr(0, 1, "[", color)
        win.addstr(0, 2 + len(lbl_title), "]", color)
        win.addstr(h + 1, 1, "[", color)
        win.addstr(h + 1, 2 + len(lbl_esc), "]", color)

        color = get_color(UI_TITLES)
        win.addstr(0, 2, lbl_title, color)
        win.addstr(h + 1, 2, lbl_esc, color)
        self.scroll = ScrollCalc(len(items), h)
        return win

    def show(self):
        while True:
            self.draw(self.win, self.items, self.cursor, self.scroll)
            self.win.refresh()
            #
            key = stdscr.getch()
            #
            if key == curses.KEY_RESIZE:
                set_term_size()
                stdscr.clear()
                stdscr.refresh()
                self.win = self.init_win(self.items, self.title, self.win)
                self.resized = True
            elif key in keys.s_enter:
                return self.cursor + 1  # return 1-based index
            elif key in keys.r_quit:
                return False  #
            else:
                self.on_key_pressed(key, self.scroll)

    @staticmethod
    def draw(win, items, cursor, scroll):
        h, w = win.getmaxyx()
        if h < 3 or w < 5:
            if h > 0 and w > 0:
                win.insstr(0, 0, "#" * w)
            return  # no space to draw
        #
        scroll.ensure_visible(cursor)
        for i, item in enumerate(items[scroll.pos:scroll.pos + h - 2]):
            color = get_color(UI_TEXT if i + scroll.pos != cursor else
                              UI_CURSOR)
            win.addstr(i + 1, 1, " " * (w - 2), color)
            win.addstr(i + 1, 1, item[:w - 2], color)

        if scroll.is_scrollable:
            draw_scrollbarV(win, 1, w - 1, scroll)

    def on_key_pressed(self, key, scroll):  # type: (int, ScrollCalc) -> None
        if key in keys.r_up:
            self.cursor -= 1
            if self.cursor < 0:
                self.cursor = scroll.content - 1
        elif key in keys.r_down:
            self.cursor += 1
            if self.cursor >= self.scroll.content:
                self.cursor = 0
        elif key in keys.r_home:
            self.cursor = 0
        elif key in keys.r_mend:
            self.cursor = scroll.content - 1
        elif key in keys.r_ppage:
            if self.cursor > scroll.pos:
                self.cursor = scroll.pos
            else:
                self.cursor = max(0, self.cursor - scroll.view)
        elif key in keys.r_npage:
            page_bottom = scroll.pos_bottom()
            if self.cursor < page_bottom:
                self.cursor = page_bottom
            else:
                self.cursor = min(scroll.content - 1, page_bottom + scroll.view)


# region Render Body
def render_body(scr, tokens, scroll):
    # type: (curses.window, List[parser.Token], int) -> None
    h, w = scr.getmaxyx()
    tnum, offset = parser.find_visible_token(tokens, scroll)
    line_num = tokens[tnum].line_num
    for y in range(5, h - 1):
        scr.addstr(y, 0, " " * w, 1)
    y, x = (5, 0)
    text_attr = 0
    if parser.INLINE_STYLE_ENABLED:
        # Rewind tokens from the begin of line to apply inline text attributes
        first_token = tnum
        while tokens[first_token].line_num == line_num and first_token > 0:
            first_token -= 1
        for token in tokens[first_token:tnum]:
            text_attr = apply_attribute(token, text_attr)

    for token in tokens[tnum:]:
        if token.line_num > line_num:
            line_num = token.line_num
            y, x = (y + 1, 0)
        if y >= h - 1:
            break  # tokens
        #
        text_attr = apply_attribute(token, text_attr)
        #
        y, x = render_token(scr, token, y, x, h, offset, text_attr)
        offset = 0  # required in the first partial multiline token only


def apply_attribute(token, text_attr):
    if token.type == parser.TT.URL:
        text_attr |= curses.A_UNDERLINE
    else:
        text_attr &= ~curses.A_UNDERLINE

    if token.type == parser.TT.ITALIC_BEGIN:
        text_attr |= curses.A_ITALIC
    elif token.type == parser.TT.ITALIC_END:
        text_attr &= ~curses.A_ITALIC

    elif token.type == parser.TT.BOLD_BEGIN:
        text_attr |= curses.A_BOLD
    elif token.type == parser.TT.BOLD_END:
        text_attr &= ~curses.A_BOLD
    return text_attr


def render_token(scr, token: parser.Token, y, x, h, offset, text_attr):
    for i, line in enumerate(token.render[offset:]):
        if y + i >= h - 1:
            return y + i, x  #
        attr = get_color(TOKEN2UI.get(token.type, UI_TEXT))
        if line:
            scr.addstr(y + i, x, line, attr | text_attr)

        if len(token.render) > 1 and i + offset < len(token.render) - 1:
            x = 0  # new line in multiline token -- carriage return
        else:
            x += len(line)  # last/single line -- move caret in line
    return y + (len(token.render) - 1) - offset, x  #
# endregion Render Body


class MsgListScreen:
    def __init__(self, echo, data, msgn):
        # type: (str, List[List[str]], int) -> MsgListScreen
        self.data = data
        self.echo = echo
        self.cursor = msgn
        self.scroll = ScrollCalc(len(self.data), HEIGHT - 2)
        self.scroll.ensure_visible(self.cursor, center=True)
        self.resized = False
        self.search_ = None  # type: Optional[search.Search]

    def show(self):  # type: () -> int
        stdscr.clear()
        self.draw_title(stdscr, self.echo)
        while True:
            self.scroll.ensure_visible(self.cursor)
            self.draw(stdscr, self.data, self.cursor, self.scroll)
            if self.search_:
                self.search_.draw(stdscr, HEIGHT - 1,
                                  len(version) + 2,
                                  WIDTH - len(version) - 12,
                                  get_color(UI_STATUS))
            #
            ks, key, _ = get_keystroke()
            #
            if key == curses.KEY_RESIZE:
                set_term_size()
                stdscr.clear()
                self.scroll = ScrollCalc(len(self.data), HEIGHT - 2)
                self.draw_title(stdscr, self.echo)
                self.resized = True
            elif self.search_:
                if key in keys.s_csearch:
                    self.search_ = None
                    curses.curs_set(0)
                else:
                    self.cursor = self.search_.on_key_pressed_search(
                        key, ks, self.scroll, self.cursor)
            elif key in keys.s_enter:
                return self.cursor  #
            elif key in keys.r_quit:
                return -1  #
            else:
                self.on_key_pressed(key, self.scroll)

    @staticmethod
    def draw_title(win, echo):
        _, w = win.getmaxyx()
        color = get_color(UI_BORDER)
        win.addstr(0, 0, "─" * w, color)
        if w >= 80:
            draw_title(win, 0, 0, "Список сообщений в конференции " + echo)
        else:
            draw_title(win, 0, 0, echo)

    def draw(self, win, data, cursor, scroll):
        h, w = win.getmaxyx()
        for i in range(1, h - 1):
            color = get_color(UI_TEXT if scroll.pos + i - 1 != cursor else
                              UI_CURSOR)
            win.addstr(i, 0, " " * w, color)
            pos = scroll.pos + i - 1
            if pos >= scroll.content:
                continue  #
            #
            msg = data[pos]
            win.addstr(i, 0, msg[1], color)
            win.addstr(i, 16, msg[2][:w - 27], color)
            win.addstr(i, w - 11, msg[3], color)
            #
            if self.search_ and pos in self.search_.result:
                idx = self.search_.result.index(pos)
                m_name, m_subj = self.search_.matches[idx]
                for m in m_name:
                    win.addstr(i, 0 + m.start(), msg[1][m.start():m.end()],
                               color | curses.A_REVERSE)
                for m in m_subj:
                    end = min(w - 27, m.end())
                    if m.start() + 16 > w - 12:
                        continue
                    win.addstr(i, 16 + m.start(), msg[2][m.start():end],
                               color | curses.A_REVERSE)

        #
        if scroll.is_scrollable:
            draw_scrollbarV(win, 1, w - 1, scroll)
        draw_status_bar(win, text=utils.msgn_status(data, cursor, w))

    def on_key_pressed(self, key, scroll):
        if key in keys.s_up:
            self.cursor = max(0, self.cursor - 1)
        elif key in keys.s_down:
            self.cursor = min(scroll.content - 1, self.cursor + 1)
        elif key in keys.s_ppage:
            if self.cursor > scroll.pos:
                self.cursor = scroll.pos
            else:
                self.cursor = max(0, self.cursor - scroll.view)
        elif key in keys.s_npage:
            page_bottom = scroll.pos_bottom()
            if self.cursor < page_bottom:
                self.cursor = page_bottom
            else:
                self.cursor = min(scroll.content - 1, page_bottom + scroll.view)
        elif key in keys.s_home:
            self.cursor = 0
        elif key in keys.s_end:
            self.cursor = scroll.content - 1
        elif key in keys.s_osearch:
            curses.curs_set(1)
            stdscr.move(HEIGHT - 1, len(version) + 2)
            self.search_ = search.Search(self.data, self.on_search_item)

    @staticmethod
    def on_search_item(pattern, it):
        result_name = []
        result_subj = []
        p = 0
        while match := pattern.search(it[1], p):
            result_name.append(match)
            p = match.end()
        p = 0
        while match := pattern.search(it[2], p):
            result_subj.append(match)
            p = match.end()
        if result_name or result_subj:
            return result_name, result_subj
        return None
