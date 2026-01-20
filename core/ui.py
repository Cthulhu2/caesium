import curses
from typing import Optional, List

from core import config

HEIGHT = 0
WIDTH = 0

stdscr = None  # type: Optional[curses.window]


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


def draw_splash(scr, splash):  # type: (curses.window, List[str]) -> None
    scr.clear()
    h, w = scr.getmaxyx()
    x = int((w - len(splash[1])) / 2) - 1
    y = int((h - len(splash)) / 2)
    color = config.get_color("text")
    for i, line in enumerate(splash):
        scr.addstr(y + i, x, line, color)
    scr.refresh()


def draw_message_box(smsg, wait):
    msg = smsg.split("\n")
    maxlen = max(map(lambda x: len(x), msg))
    any_key = "Нажмите любую клавишу"
    if wait:
        maxlen = max(len(any_key), maxlen)
        win = curses.newwin(len(msg) + 4,
                            maxlen + 2,
                            int(HEIGHT / 2 - 2),
                            int(WIDTH / 2 - maxlen / 2 - 2))
    else:
        win = curses.newwin(len(msg) + 2,
                            maxlen + 2,
                            int(HEIGHT / 2 - 2),
                            int(WIDTH / 2 - maxlen / 2 - 2))
    win.bkgd(' ', config.get_color("text"))
    win.attrset(config.get_color("border"))
    win.border()

    color = config.get_color("text")
    for i, line in enumerate(msg, start=1):
        win.addstr(i, 1, line, color)

    color = config.get_color("titles")
    if wait:
        win.addstr(len(msg) + 2, int((maxlen + 2 - 21) / 2), any_key, color)
    win.refresh()


def show_message_box(smsg):
    draw_message_box(smsg, True)
    stdscr.getch()
    stdscr.clear()
