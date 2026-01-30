import curses
import re

import keys.default as keys
from core import ui

LABEL_SEARCH = "<введите regex для поиска>"


class Pager:
    pos: int = 0

    def __init__(self, pos, next_after, prev_before):
        self.pos = pos
        self.next_after = next_after
        self.prev_before = prev_before

    def next_after(self):
        pass

    def prev_before(self):
        pass


class QuickSearch:
    def __init__(self, items, matcher, width=0):
        self.items = items
        self.query = ""
        self.matches = []
        self.result = []
        self.idx = 0
        self.err = ""
        self.matcher = matcher
        self.width = width

    def draw(self, win, y, x, color):
        # type: (curses.window, int, int, int) -> None
        win.addstr(y, x, " " * (self.width or len(self.query)), color)
        if self.query:
            idx = self.idx + 1 if self.result else 0
            line = "%s  (%s%d / %d)" % (self.query, self.err, idx, len(self.result))
            win.addnstr(y, x, line, self.width or len(line), color)
        else:
            win.addstr(y, x, LABEL_SEARCH, color)
        win.move(y, x + len(self.query))

    def search(self, query, pos):
        self.result = []
        self.matches = []
        self.idx = -1
        self.query = query
        self.err = ""
        if not query:
            return  #
        try:
            template = re.compile(query, re.IGNORECASE)
        except re.error:
            self.err = "err "
            return  # error

        sidx = 0
        for i, item in enumerate(self.items):
            if matches := self.matcher(sidx, template, item):
                for m in matches:
                    self.result.append(i)
                    self.matches.append(m)
                    sidx += 1
                    if self.idx == -1 and i >= pos:
                        self.idx = len(self.result) - 1

    @staticmethod
    def _next_page_top_pos(pager):
        if isinstance(pager, ui.ScrollCalc):
            return pager.pos + pager.view
        return pager.next_after()

    @staticmethod
    def _prev_page_bottom_pos(pager):
        if isinstance(pager, ui.ScrollCalc):
            return pager.pos
        return pager.prev_before()

    def on_key_pressed_search(self, key, keystroke, pager):
        if "Space" == keystroke:
            keystroke = " "
        if key in keys.s_home:
            self.home()
        elif key in keys.s_end:
            self.end()
        elif key in keys.s_down:
            self.next()
        elif key in keys.s_up:
            self.prev()
        elif key in keys.s_npage:
            self.next_after(self._next_page_top_pos(pager))
        elif key in keys.s_ppage:
            self.prev_before(self._prev_page_bottom_pos(pager))
        elif key in (curses.KEY_BACKSPACE, 127):
            # 127 - Ctrl+? - Android backspace
            self.search(self.query[0:-1], pager.pos)
        elif len(keystroke) == 1 and (not self.width
                                      or len(self.query) < self.width):
            self.search(self.query + keystroke, pager.pos)

    def home(self):
        self.idx = 0

    def end(self):
        self.idx = len(self.result) - 1

    def next(self):
        self.idx += 1
        if self.idx >= len(self.result):
            self.idx = 0

    def prev(self):
        self.idx -= 1
        if self.idx < 0:
            self.idx = len(self.result) - 1

    def next_after(self, pos):
        if not self.result:
            return  #
        init = self.idx
        while self.result[self.idx] < pos:
            self.idx += 1
            if self.idx >= len(self.result):
                self.idx = 0
            if self.idx == init:
                self.end()
                break  #

    def prev_before(self, pos):
        if not self.result:
            return  #
        init = self.idx
        while self.result[self.idx] > pos:
            self.idx -= 1
            if self.idx < 0:
                self.idx = len(self.result) - 1
            if self.idx == init:
                self.home()
                break  #
