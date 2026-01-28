import curses
import re

import keys.default as keys

LABEL_SEARCH = "<введите текст для поиска>"


class Search:
    def __init__(self, items, searcher):
        self.items = items
        self.query = ""
        self.matches = []
        self.result = []
        self.idx = 0
        self.first = 0
        self.last = 0
        self.searcher = searcher

    def draw(self, win, y, x, w, color,):
        # type: (curses.window, int, int, int, int) -> None
        win.addstr(y, x, " " * w, color)
        if self.query:
            win.addstr(y, x, self.query, color)
        else:
            win.addstr(y, x, LABEL_SEARCH, color)
        win.move(y, x + len(self.query))

    def search(self, query, pos):
        self.result = []
        self.matches = []
        self.idx = 0
        self.first = 0
        self.last = 0
        self.query = query
        if not query:
            return  #
        template = re.compile(query, re.IGNORECASE)

        def search_item(it, idx):
            if result_item := self.searcher(template, it):
                self.result.append(idx)
                self.matches.append(result_item)

        for i, item in enumerate(self.items[pos:], start=pos):
            search_item(item, i)
        for i, item in enumerate(self.items[0:pos]):
            search_item(item, i)

        if self.result:
            self.first = self.result.index(min(self.result))
            self.last = self.result.index(max(self.result))

    def on_key_pressed_search(self, key, keystroke, scroll, cursor):
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
            self.next_after(scroll.pos + scroll.view)
            if self.result:
                cursor = self.result[self.idx]
                scroll.pos = cursor
        elif key in keys.r_ppage:
            self.prev_before(scroll.pos)
            if self.result:
                cursor = self.result[self.idx]
                scroll.pos = cursor - scroll.view + 1
        elif key in (curses.KEY_BACKSPACE, 127):
            # 127 - Ctrl+? - Android backspace
            self.search(self.query[0:-1], scroll.pos)
        elif len(keystroke) == 1:
            self.search(self.query + keystroke, scroll.pos)
        if self.result:
            cursor = self.result[self.idx]
            scroll.ensure_visible(cursor, center=True)
        return cursor

    def home(self):
        self.idx = self.first

    def end(self):
        self.idx = self.last

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
                self.idx = self.last
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
                self.idx = self.first
                break  #
