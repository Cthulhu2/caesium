#!/usr/bin/env python3
# coding=utf-8
import base64
import codecs
import curses
import hashlib
import locale
import os
import pickle
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from shutil import copyfile
from typing import List, Dict, Union, Tuple

import keys

# TODO: Add http/https/socks proxy support
# import socket
# import socks
# socks.set_default_proxy(socks.SOCKS5, '127.0.0.1', 8081)
# socket.socket = socks.socksocket

# Theme
color_theme = "default"
color_pairs = {
    # "ui-element": [color-pair-NUM, bold-attr]
    # @formatter:off
    "border":     [1,  0],
    "titles":     [2,  0],
    "cursor":     [3,  0],
    "text":       [4,  0],
    "quote1":     [5,  0],
    "quote2":     [6,  0],
    "comment":    [7,  0],
    "url":        [8,  0],
    "statusline": [9,  0],
    "header":     [10, 0],
    "scrollbar":  [11, 0],
    "origin":     [12, 0],
    # @formatter:on
}
can_change_color = False


def get_color(theme_part):
    cp = color_pairs[theme_part][0]
    bold = color_pairs[theme_part][1]
    return curses.color_pair(cp) | bold


lasts = {}
if os.path.exists("lasts.lst"):
    with open("lasts.lst", "rb") as f_lasts:
        lasts = pickle.load(f_lasts)
counts = []
counts_rescan = True
echo_counts = {}
next_echoarea = False
messages = []
twit = []
nodes = []  # type: List[Dict[str, Union[str, List[Union[str, Tuple[str, str, bool]]]]]]
node = 0
editor = ""
oldquote = False
db = "ait"
browser = webbrowser

version = "Caesium/0.5 │"

splash = ["▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀",
          "████████ ████████ ████████ ████████ ███ ███  ███ ██████████",
          "███           ███ ███  ███ ███          ███  ███ ███ ██ ███",
          "███      ████████ ████████ ████████ ███ ███  ███ ███ ██ ███",
          "███      ███  ███ ███           ███ ███ ███  ███ ███ ██ ███",
          "████████ ████████ ████████ ████████ ███ ████████ ███ ██ ███",
          "▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄",
          "           ncurses ii/idec client      v.0.5",
          "           Andrew Lobanov             01.11.2024"]

url_template = re.compile(r"((https?|ftp|file)://?[-A-Za-z0-9+&@#/%?=~_|!:,.;]+[-A-Za-z0-9+&@#/%=~_|])")
# noinspection RegExpRedundantEscape
ps_template = re.compile(r"(^\s*)(PS|P.S|ps|ЗЫ|З.Ы|\/\/|#)")
# noinspection RegExpRedundantEscape
quote_template = re.compile(r"^[a-zA-Zа-яА-Я0-9_\-.\(\)]{0,20}>{1,20}")


def reset_config():
    global nodes, node, editor, oldquote, db
    nodes = []
    node = 0
    editor = ""
    oldquote = False
    db = "ait"


def check_directories():
    if not os.path.exists("out"):
        os.mkdir("out")
    for n in nodes:
        if not os.path.exists("out/" + n["nodename"]):
            os.mkdir("out/" + n["nodename"])
    api.init()


def check_config():
    if not os.path.exists("caesium.cfg"):
        default_config = open("caesium.def.cfg", "r").read()
        open("caesium.cfg", "w").write(default_config)


#
# Взаимодействие с нодой
#
def separate(fetch_list, step=20):
    for x in range(0, len(fetch_list), step):
        yield fetch_list[x:x + step]


def load_config():
    global nodes, editor, color_theme, show_splash, oldquote, db, browser, twit
    nodes = []
    first = True
    browser = webbrowser
    # current node
    cnode = {}  # type: Dict[str, Union[str, List[Union[str, Tuple[str, str, bool]]]]]
    echoareas = []  # type: List[Tuple[str, str, bool]]
    archive = []  # type: List[Tuple[str, str, bool]]
    #
    config = open("caesium.cfg").read().split("\n")
    shrink_spaces = re.compile(r"(\s\s+|\t+)")
    for line in config:
        param = shrink_spaces.sub(" ", line.strip()).split(" ", maxsplit=2)
        if param[0] == "nodename":
            if not first:
                cnode["echoareas"] = echoareas
                cnode["archive"] = archive
                if "to" not in cnode:
                    cnode["to"] = []
                nodes.append(cnode)
            else:
                first = False
            cnode = {}
            echoareas = []
            archive = []
            cnode["nodename"] = " ".join(param[1:])
        elif param[0] == "node":
            cnode["node"] = param[1]
            if not cnode["node"].endswith("/"):
                cnode["node"] += "/"
        elif param[0] == "auth":
            cnode["auth"] = param[1]
        elif param[0] == "echo":
            echoareas.append((param[1], "".join(param[2:]), False))
        elif param[0] == "stat":
            echoareas.append((param[1], "".join(param[2:]), True))
        elif param[0] == "to":
            cnode["to"] = " ".join(param[1:]).split(",")
        elif param[0] == "archive":
            archive.append((param[1], "".join(param[2:]), True))
        #
        elif param[0] == "editor":
            editor = " ".join(param[1:])
        elif param[0] == "theme":
            color_theme = param[1]
        elif param[0] == "nosplash":
            show_splash = False
        elif param[0] == "oldquote":
            oldquote = True
        elif param[0] == "db":
            db = param[1]
        elif param[0] == "browser":
            browser = webbrowser.GenericBrowser(param[1])
        elif param[0] == "twit":
            twit = param[1].split(",")

    if "nodename" not in cnode:
        cnode["nodename"] = "untitled node"
    if "to" not in cnode:
        cnode["to"] = []
    cnode["echoareas"] = echoareas
    cnode["archive"] = archive
    nodes.append(cnode)
    for i in range(0, len(nodes)):
        nodes[i]["echoareas"].insert(0, ("favorites", "Избранные сообщения", True))
        nodes[i]["echoareas"].insert(1, ("carbonarea", "Карбонка", True))


def init_hex_color(color, cache, idx):
    if not can_change_color:
        raise ValueError("No extended color support in the terminal "
                         + str(curses.termname()))

    if len(color) == 7 and color[0] == "#":
        r = int("0x" + color[1:3], 16)
        g = int("0x" + color[3:5], 16)
        b = int("0x" + color[5:7], 16)
    elif len(color) == 4 and color[0] == "#":
        r = int("0x" + color[1] * 2, 16)
        g = int("0x" + color[2] * 2, 16)
        b = int("0x" + color[3] * 2, 16)
    else:
        raise ValueError("Invalid color value :: " + color)
    if (r, g, b) in cache:
        return cache[(r, g, b)], False
    curses_r = int(round(r / 255 * 1000))  # to 0..1000
    curses_g = int(round(g / 255 * 1000))
    curses_b = int(round(b / 255 * 1000))
    curses.init_color(idx, curses_r, curses_g, curses_b)
    cache[(r, g, b)] = idx
    return idx, True


def load_colors(theme):
    colors = ["black", "red", "green", "yellow", "blue",
              "magenta", "cyan", "white",
              "brblack", "brred", "brgreen", "bryellow", "brblue",
              "brmagenta", "brcyan", "brwhite"]
    c256cache = {}
    c256idx = curses.COLORS - 1
    shrink_spaces = re.compile(r"(\s\s+|\t+)")
    color3_regex = re.compile(r"#[a-fA-F0-9]{3}")
    color6_regex = re.compile(r"#[a-fA-F0-9]{6}")
    for line in open("themes/" + theme + ".cfg", "r").readlines():
        # sanitize
        line = shrink_spaces.sub(" ", line.strip())
        nocolor = color3_regex.sub("-" * 4, color6_regex.sub("-" * 7, line))
        if "#" in nocolor:
            line = line[0:nocolor.index("#")].strip()  # skip comments
        if not line:
            continue
        params = line.split(" ")
        if (len(params) not in (3, 4)
                or params[0] not in color_pairs
                or len(params) == 4 and params[3] != "bold"):
            raise ValueError("Invalid theme params :: " + line)
        # foreground
        if params[1].startswith("#"):
            fg, idxChange = init_hex_color(params[1], c256cache, c256idx)
            if idxChange:
                c256idx -= 1
        elif params[1].startswith("color"):
            fg = int(params[1][5:])
        else:
            fg = colors.index(params[1])
        # background
        if params[2] == "default":
            bg = -1
        elif params[2].startswith("#"):
            bg, idxChange = init_hex_color(params[2], c256cache, c256idx)
            if idxChange:
                c256idx -= 1
        elif params[2].startswith("color"):
            bg = int(params[2][5:])
        else:
            bg = colors.index(params[2])
        # bold
        color_pairs[params[0]][1] = curses.A_NORMAL
        if len(params) == 4:
            color_pairs[params[0]][1] = curses.A_BOLD
        #
        curses.init_pair(color_pairs[params[0]][0], fg, bg)


def save_out(draft=False):
    new = codecs.open("temp", "r", "utf-8").read().strip().replace("\r", "").split("\n")
    if len(new) <= 1:
        os.remove("temp")
    else:
        header = new.index("")
        if header == 3:
            buf = new
        elif header == 4:
            buf = new[1:5] + ["@repto:%s" % new[0]] + new[5:]
        else:
            buf = ()
        if draft:
            codecs.open(outcount() + ".draft", "w", "utf-8").write("\n".join(buf))
        else:
            codecs.open(outcount() + ".out", "w", "utf-8").write("\n".join(buf))
        os.remove("temp")


def resave_out(filename, draft=False):
    new = codecs.open("temp", "r", "utf-8").read().strip().split("\n")
    if len(new) <= 1:
        os.remove("temp")
    else:
        if draft:
            codecs.open("out/" + nodes[node]["nodename"] + "/" + filename.replace(".out", ".draft"), "w",
                        "utf-8").write("\n".join(new))
        else:
            codecs.open("out/" + nodes[node]["nodename"] + "/" + filename, "w", "utf-8").write("\n".join(new))
        os.remove("temp")


def outcount():
    outpath = "out/" + nodes[node]["nodename"]
    i = str(len([x for x in os.listdir(outpath)
                 if not x.endswith(".toss")]) + 1)
    return outpath + "/%s" % i.zfill(5)


def get_out_length(drafts=False):
    node_dir = "out/" + nodes[node]["nodename"]
    if drafts:
        return len([f for f in sorted(os.listdir(node_dir))
                    if f.endswith(".draft")]) - 1
    else:
        return len([f for f in sorted(os.listdir(node_dir))
                    if f.endswith(".out") or f.endswith(".outmsg")]) - 1


def make_toss():
    node_dir = "out/" + nodes[node]["nodename"]
    lst = [x for x in os.listdir(node_dir)
           if x.endswith(".out")]
    for msg in lst:
        text_raw = codecs.open(node_dir + "/%s" % msg, "r", "utf-8").read()
        text_b64 = base64.b64encode(text_raw.encode("utf-8")).decode("utf-8")
        codecs.open(node_dir + "/%s.toss" % msg, "w", "utf-8").write(text_b64)
        os.rename(node_dir + "/%s" % msg,
                  node_dir + "/%s%s" % (msg, "msg"))


def send_mail():
    lst = [x for x in sorted(os.listdir("out/" + nodes[node]["nodename"]))
           if x.endswith(".toss")]
    total = str(len(lst))
    try:
        node_dir = "out/" + nodes[node]["nodename"]
        for n, msg in enumerate(lst, start=1):
            print("\rОтправка сообщения: " + str(n) + "/" + total, end="")
            msg_toss = node_dir + "/%s" % msg
            text = codecs.open(msg_toss, "r", "utf-8").read()
            #
            data = urllib.parse.urlencode({
                "tmsg": text,
                "pauth": nodes[node]["auth"],
            }).encode("utf-8")
            req = urllib.request.Request(nodes[node]["node"] + "u/point")
            result = urllib.request.urlopen(req, data).read().decode("utf-8")
            #
            if result.startswith("msg ok"):
                os.remove(msg_toss)
            elif result == "msg big!":
                print("\nERROR: very big message (limit 64K)!")
            elif result == "auth error!":
                print("\nERROR: unknown auth!")
            else:
                print("\nERROR: unknown error!")
        if len(lst) > 0:
            print()
    except Exception as ex:
        print("\nОшибка: не удаётся связаться с нодой. " + str(ex))


def get_msg_list():
    msg_list = []
    echoareas = "/".join(map(
        lambda echo: echo[0],  # echo name
        filter(lambda echo: not echo[2],  # skip stat, carbonarea, favorites
               nodes[node]["echoareas"])))
    if echoareas:
        r = urllib.request.Request(nodes[node]["node"] + "u/e/" + echoareas)
        with urllib.request.urlopen(r) as f:
            lines = f.read().decode("utf-8").split("\n")
            for line in lines:
                if len(line) > 0:
                    msg_list.append(line)
    return msg_list


def get_bundle(node_url, msgids):
    r = urllib.request.Request(node_url + "u/m/" + msgids)
    with urllib.request.urlopen(r) as f:
        bundle = f.read().decode("utf-8").split("\n")
    return bundle


def debundle(bundle):
    global messages
    for msg in bundle:
        if msg:
            m = msg.split(":")
            msgid = m[0]
            if len(msgid) == 20 and m[1]:
                msgbody = base64.b64decode(m[1].encode("ascii")).decode("utf8").split("\n")
                messages.append([msgid, msgbody])

    if len(messages) >= 1000:
        api.save_message(messages, nodes[node]["node"], nodes[node]["to"])
        messages = []


def echo_filter(ea):
    rr = re.compile(r'^[a-z0-9_!.-]{1,60}\.[a-z0-9_!.-]{1,60}$')
    if rr.match(ea):
        return True


def get_mail():
    fetch_msg_list = []
    print("Получение индекса от ноды...")
    remote_msg_list = get_msg_list()
    print("Построение разностного индекса...")
    local_index = None
    for line in remote_msg_list:
        if echo_filter(line):
            local_index = api.get_echo_msgids(line)
        else:
            if line not in local_index:
                fetch_msg_list.append(line)
    if fetch_msg_list:
        total = str(len(fetch_msg_list))
        count = 0
        for get_list in separate(fetch_msg_list):
            count += len(get_list)
            print("\rПолучение сообщений: " + str(count) + "/" + total, end="")
            debundle(get_bundle(nodes[node]["node"], "/".join(get_list)))
        api.save_message(messages, node, nodes[node]["to"])
    else:
        print("Новых сообщений не обнаружено.", end="")
    print()


def fetch_mail():
    print("Работа с " + nodes[node]["node"])
    try:
        if "auth" in nodes[node]:
            make_toss()
            send_mail()
        get_mail()
    except KeyboardInterrupt:
        print("\nПрервано пользователем")
    except Exception as ex:
        print("\nОШИБКА: " + str(ex))
    input("Нажмите Enter для продолжения.")


#
# Пользовательский интерфейс
#
echo_cursor = 0
archive_cursor = 0
width = 0
height = 0
show_splash = True


def splash_screen():
    stdscr.clear()
    x = int((width - len(splash[1])) / 2) - 1
    y = int((height - len(splash)) / 2)
    i = 0
    for line in splash:
        stdscr.addstr(y + i, x, line, get_color("text"))
        i = i + 1
    stdscr.refresh()
    curses.napms(2000)
    stdscr.clear()


def get_term_size():
    global width, height
    height, width = stdscr.getmaxyx()


def draw_title(y, x, title):
    x = max(0, x)
    if (x + len(title) + 2) > width:
        title = title[:width - x - 2 - 3] + '...'
    #
    color = get_color("border")
    stdscr.addstr(y, x, "[", color)
    stdscr.addstr(y, x + 1 + len(title), "]", color)
    color = get_color("titles")
    stdscr.addstr(y, x + 1, title, color)


def draw_status(x, title):
    color = get_color("statusline")
    stdscr.addstr(height - 1, x, title, color)


def draw_cursor(y, color):
    stdscr.insstr(y + 1, 0, " " * width, color)


def current_time():
    draw_status(width - 8, "│ " + datetime.now().strftime("%H:%M"))


# noinspection PyUnusedLocal
def get_counts(new=False, favorites=False):
    global echo_counts
    for echoarea in nodes[node]["echoareas"]:
        if not new:
            if not echoarea[0] in echo_counts:
                echo_counts[echoarea[0]] = api.get_echo_length(echoarea[0])
        else:
            echo_counts[echoarea[0]] = api.get_echo_length(echoarea[0])
    for echoarea in nodes[node]["archive"]:
        if not echoarea[0] in echo_counts:
            echo_counts[echoarea[0]] = api.get_echo_length(echoarea[0])
    echo_counts["carbonarea"] = len(api.get_carbonarea())
    echo_counts["favorites"] = len(api.get_favorites_list())


def rescan_counts(echoareas):
    counts_ = []
    for echo in echoareas:
        echocount = echo_counts[echo[0]]
        if echo[0] in lasts:
            last = echocount - lasts[echo[0]]
            if echocount == 0 and lasts[echo[0]] == 0:
                last = 1
        else:
            last = echocount + 1

        if last - 1 < 0:
            last = 1
        counts_.append([str(echocount), str(last - 1)])
    return counts_


def draw_echo_selector(start, cursor, archive):
    global counts, counts_rescan
    dsc_lens = []
    hidedsc = False
    m = 0
    stdscr.attrset(get_color("border"))
    color = get_color("border")
    stdscr.insstr(0, 0, "─" * width, color)
    color = get_color("statusline")
    stdscr.insstr(height - 1, 0, " " * width, color)
    if archive:
        echoareas = nodes[node]["archive"]
        draw_title(0, 0, "Архив")
    else:
        echoareas = nodes[node]["echoareas"]
        draw_title(0, 0, "Конференция")
    draw_status(1, version)
    draw_status(len(version) + 2, nodes[node]["nodename"])
    for echo in echoareas:
        desc_len = len(echo[1])
        if desc_len > m:
            m = desc_len
        if m > width - 38:
            m = width - 38
        dsc_lens.append(desc_len)
    y = 0
    count = "Сообщений"
    unread = "Не прочитано"
    description = "Описание"
    if width < 80 or m == 0:
        m = len(unread) - 7
        hidedsc = True
    draw_title(0, width + 2 - m - len(count) - len(unread) - 1, count)
    draw_title(0, width - 8 - m - 1, unread)
    if not hidedsc:
        draw_title(0, width - len(description) - 2, description)
    for echo in echoareas:
        if y - start < height - 2:
            if y == cursor:
                if y >= start:
                    color = get_color("cursor")
                    stdscr.attrset(color)
                    draw_cursor(y - start, color)
            else:
                if y >= start:
                    color = get_color("text")
                    draw_cursor(y - start, color)
                stdscr.attrset(get_color("text"))
            if y + 1 >= start + 1:
                if counts_rescan:
                    counts = rescan_counts(echoareas)
                    counts_rescan = False
                echo_length = int(counts[y][0])
                if echo[0] in lasts:
                    last = lasts[echo[0]]
                else:
                    last = -1
                if last < echo_length - 1 or last == -1 and echo_length == 1:
                    stdscr.addstr(y + 1 - start, 0, "+")
                stdscr.addstr(y + 1 - start, 2, echo[0])
                if width >= 80:
                    if width - 38 >= len(echo[1]):
                        stdscr.addstr(y + 1 - start, width - 1 - dsc_lens[y], echo[1], color)
                    else:
                        cut_index = width - 38 - len(echo[1])
                        stdscr.addstr(y + 1 - start, width - 1 - len(echo[1][:cut_index]), echo[1][:cut_index])
                stdscr.addstr(y + 1 - start, width - 10 - m - len(counts[y][0]), counts[y][0])
                stdscr.addstr(y + 1 - start, width - 2 - m - len(counts[y][1]), counts[y][1])
        y = y + 1
    current_time()
    stdscr.refresh()


def find_new(cursor):
    ret = cursor
    n = 0
    lock = False
    for i in counts:
        n = n + 1
        if n > cursor and not lock and int(i[1]) > 0:
            ret = n - 1
            lock = True
    return ret


def edit_config():
    global stdscr
    curses.echo()
    curses.curs_set(True)
    curses.endwin()
    p = subprocess.Popen(editor + " ./caesium.cfg", shell=True)
    p.wait()
    reset_config()
    load_config()
    stdscr = curses.initscr()
    curses.start_color()
    curses.use_default_colors()
    curses.noecho()
    curses.curs_set(False)
    stdscr.keypad(True)
    get_term_size()


def show_echo_selector_screen():
    global echo_cursor, archive_cursor, counts, counts_rescan, next_echoarea, node, stdscr
    archive = False
    echoareas = nodes[node]["echoareas"]
    go = True
    start = 0
    if archive:
        cursor = echo_cursor
    else:
        cursor = archive_cursor
    while go:
        draw_echo_selector(start, cursor, archive)
        key = stdscr.getch()
        if key == curses.KEY_RESIZE:
            get_term_size()
            if cursor >= height - 2:
                start = cursor - height + 3
            if cursor - start <= 0:
                start = cursor
            if start > 0 and height - 2 > len(echoareas):
                start = 0
            stdscr.clear()
        elif key in keys.s_up and cursor > 0:
            cursor = cursor - 1
            if cursor - start < 0 < start:
                start = start - 1
        elif key in keys.s_down and cursor < len(echoareas) - 1:
            cursor = cursor + 1
            if cursor - start > height - 3 and start < len(echoareas) - height + 2:
                start = start + 1
        elif key in keys.s_ppage:
            cursor = cursor - height + 2
            if cursor < 0:
                cursor = 0
            if cursor - start < 0 < start:
                start = start - height + 2
            if start < 0:
                start = 0
        elif key in keys.s_npage:
            cursor = cursor + height - 2
            if cursor >= len(echoareas):
                cursor = len(echoareas) - 1
            if cursor - start > height - 3:
                start = start + height - 2
                if start > len(echoareas) - height + 2:
                    start = len(echoareas) - height + 2
        elif key in keys.s_home:
            cursor = 0
            start = 0
        elif key in keys.s_end:
            cursor = len(echoareas) - 1
            if len(echoareas) >= height - 2:
                start = len(echoareas) - height + 2
        elif key in keys.s_get:
            curses.echo()
            curses.curs_set(True)
            curses.endwin()
            os.system('cls' if os.name == 'nt' else 'clear')
            fetch_mail()
            stdscr = curses.initscr()
            curses.start_color()
            curses.use_default_colors()
            curses.noecho()
            curses.curs_set(False)
            stdscr.keypad(True)
            get_term_size()
            draw_message_box("Подождите", False)
            get_counts(True)
            stdscr.clear()
            counts = rescan_counts(echoareas)
            cursor = find_new(0)
            if cursor >= height - 2:
                start = cursor - height + 3
            if cursor - start <= 0:
                start = cursor
        elif key in keys.s_archive and len(nodes[node]["archive"]) > 0:
            if archive:
                archive = False
                archive_cursor = cursor
                cursor = echo_cursor
                echoareas = nodes[node]["echoareas"]
                stdscr.clear()
                counts_rescan = True
            else:
                archive = True
                echo_cursor = cursor
                cursor = archive_cursor
                echoareas = nodes[node]["archive"]
                stdscr.clear()
                counts_rescan = True
        elif key in keys.s_enter:
            draw_message_box("Подождите", False)
            if echoareas[cursor][0] in lasts:
                last = lasts[echoareas[cursor][0]]
            else:
                last = 0
            if cursor == 0:
                echo_length = len(api.get_favorites_list())
            elif cursor == 1:
                echo_length = len(api.get_carbonarea())
            else:
                echo_length = api.get_echo_length(echoareas[cursor][0])
            if 0 < last < echo_length:
                last = last + 1
            if last >= echo_length:
                last = echo_length
            if cursor == 1:
                go = not echo_reader(echoareas[cursor], last, archive, True, False, True)
            elif cursor == 0 or echoareas[cursor][2]:
                go = not echo_reader(echoareas[cursor], last, archive, True, False, False)
            else:
                go = not echo_reader(echoareas[cursor], last, archive, False, False, False)
            counts_rescan = True
            if next_echoarea:
                counts = rescan_counts(echoareas)
                cursor = find_new(cursor)
                if cursor - start > height - 3:
                    start = cursor - height + 3
                next_echoarea = False
        elif key in keys.s_out:
            out_length = get_out_length()
            if out_length > -1:
                go = not echo_reader("out", out_length, archive, False, True, False)
        elif key in keys.s_drafts:
            out_length = get_out_length(drafts=True)
            if out_length > -1:
                go = not echo_reader("out", out_length, archive, False, True, False, True)
        elif key in keys.s_nnode:
            archive = False
            node = node + 1
            if node == len(nodes):
                node = 0
            echoareas = nodes[node]["echoareas"]
            draw_message_box("Подождите", False)
            get_counts()
            stdscr.clear()
            counts_rescan = True
            cursor = 0
            start = 0
        elif key in keys.s_pnode:
            archive = False
            node = node - 1
            if node == -1:
                node = len(nodes) - 1
            echoareas = nodes[node]["echoareas"]
            draw_message_box("Подождите", False)
            get_counts()
            stdscr.clear()
            counts_rescan = True
            cursor = 0
            start = 0
        elif key in keys.s_config:
            edit_config()
            reset_config()
            load_config()
            load_colors(color_theme)
            get_counts()
            stdscr.clear()
            counts_rescan = True
            node = 0
            archive = False
            echoareas = nodes[node]["echoareas"]
            cursor = 0
        elif key in keys.g_quit:
            go = False
    if archive:
        archive_cursor = cursor
    else:
        echo_cursor = cursor


def read_out_msg(msgid):
    node_dir = "out/" + nodes[node]["nodename"]
    temp = open(node_dir + "/" + msgid, "r").read().split("\n")
    msg = ["",
           temp[0],
           "",
           "",
           "",
           temp[1],
           temp[2]]
    for line in temp[3:]:
        if not (line.startswith("@repto:")):
            msg.append(line)
    size = os.stat(node_dir + "/" + msgid).st_size
    if size < 1024:
        size = str(size) + " B"
    else:
        size = str(int(size / 1024 * 10) / 10) + " KB"
    return msg, size


def body_render(tbody):
    body = ""
    code = ""
    sep = "─" * (width - 1)
    for line in tbody:
        n = 0
        count = 0
        qq = quote_template.match(line)
        if qq:
            count = line[0:qq.span()[1]].count(">")
        if count > 0:
            if count % 2 == 1:
                code = chr(15)
            elif count % 2 == 0:
                code = chr(16)
        elif ps_template.match(line):
            code = chr(17)
        elif line.startswith("== "):
            code = chr(18)
        else:
            code = " "
        if line == "----":
            code = chr(17)
            line = sep
        if line.startswith("+++"):
            code = chr(19)
        if code != " " and code != chr(17) and code != chr(18) and code != chr(19):
            line = " " + line
        body = body + code
        for word in line.split(" "):
            if n + len(word) < width:
                n = n + len(word)
                body = body + word
                if not word[-1:] == "\n":
                    n = n + 1
                    body = body + " "
            else:
                body = body[:-1]
                if len(word) < width:
                    body = body + "\n" + code + word
                    n = len(word)
                else:
                    chunks, chunksize = len(word), width - 1
                    chunk_list = [word[i:i + chunksize]
                                  for i in range(0, chunks, chunksize)]
                    for chunk_line in chunk_list:
                        body += "\n" + code + chunk_line
                    n = len(chunk_list[-1])
                if not word[-1:] == "\n":
                    n = n + 1
                    body = body + " "
        if body.endswith(" "):
            body = body[:-1]
        body = body + "\n"
    return body.split("\n")


def draw_reader(echo, msgid, out):
    color = get_color("border")
    stdscr.insstr(0, 0, "─" * width, color)
    stdscr.insstr(4, 0, "─" * width, color)
    color = get_color("statusline")
    stdscr.insstr(height - 1, 0, " " * width, color)
    if out:
        draw_title(0, 0, echo)
        if msgid.endswith(".out"):
            ns = "не отправлено"
            draw_title(4, width - len(ns) - 2, ns)
    else:
        if width >= 80:
            draw_title(0, 0, echo + " / " + msgid)
        else:
            draw_title(0, 0, echo)
    draw_status(1, version)
    current_time()
    for i in range(0, 3):
        draw_cursor(i, 1)
    color = get_color("titles")
    stdscr.addstr(1, 1, "От:   ", color)
    stdscr.addstr(2, 1, "Кому: ", color)
    stdscr.addstr(3, 1, "Тема: ", color)


def call_editor(out=''):
    global stdscr
    curses.echo()
    curses.curs_set(True)
    curses.endwin()
    h = hashlib.sha1(str.encode(open("temp", "r", ).read())).hexdigest()
    p = subprocess.Popen(editor + " ./temp", shell=True)
    p.wait()
    stdscr = curses.initscr()
    curses.start_color()
    curses.use_default_colors()
    curses.noecho()
    curses.curs_set(False)
    stdscr.keypad(True)
    get_term_size()
    if h != hashlib.sha1(str.encode(open("temp", "r", ).read())).hexdigest():
        d = show_menu("Куда сохранить?", ["Сохранить в исходящие",
                                          "Сохранить как черновик"])
        if d == 2:
            if not out:
                save_out(True)
            else:
                if out.endswith(".out"):
                    # noinspection PyBroadException
                    try:
                        os.remove("out/" + nodes[node]["nodename"] + "/" + out)
                    except Exception:
                        pass
                resave_out(out, draft=True)
        elif d == 1:
            if not out:
                save_out()
            else:
                if out.endswith(".draft"):
                    # noinspection PyBroadException
                    try:
                        os.remove("out/" + nodes[node]["nodename"] + "/" + out)
                    except Exception:
                        pass
                resave_out(out.replace(".draft", ".out"))
    else:
        os.remove("temp")


def draw_message_box(smsg, wait):
    msg = smsg.split("\n")
    maxlen = max(map(lambda x: len(x), msg))
    any_key = "Нажмите любую клавишу"
    if wait:
        maxlen = max(len(any_key), maxlen)
        msgwin = curses.newwin(len(msg) + 4, maxlen + 2,
                               int(height / 2 - 2),
                               int(width / 2 - maxlen / 2 - 2))
    else:
        msgwin = curses.newwin(len(msg) + 2, maxlen + 2,
                               int(height / 2 - 2),
                               int(width / 2 - maxlen / 2 - 2))
    msgwin.bkgd(' ', get_color("text"))
    msgwin.attrset(get_color("border"))
    msgwin.border()

    i = 1
    color = get_color("text")
    for line in msg:
        msgwin.addstr(i, 1, line, color)
        i = i + 1
    color = get_color("titles")
    if wait:
        msgwin.addstr(len(msg) + 2, int((maxlen + 2 - 21) / 2), any_key, color)
    msgwin.refresh()


def message_box(smsg):
    draw_message_box(smsg, True)
    stdscr.getch()
    stdscr.clear()


def save_message_to_file(msgid, echoarea):
    msg, size = api.read_msg(msgid, echoarea)
    f = open(msgid + ".txt", "w")
    f.write("== " + msg[1] + " ==================== " + str(msgid) + "\n")
    f.write("От:   " + msg[3] + " (" + msg[4] + ")\n")
    f.write("Кому: " + msg[5] + "\n")
    f.write("Тема: " + msg[6] + "\n")
    f.write("\n".join(msg[7:]))
    f.close()
    message_box("Сообщение сохранено в файл\n" + str(msgid) + ".txt")


def get_out_msgids(drafts=False):
    msgids = []
    node_dir = "out/" + nodes[node]["nodename"]
    if os.path.exists(node_dir):
        if drafts:
            msgids = [f for f in sorted(os.listdir(node_dir))
                      if f.endswith(".draft")]
        else:
            msgids = [f for f in sorted(os.listdir(node_dir))
                      if f.endswith(".out") or f.endswith(".outmsg")]
    return msgids


def quote(to):
    if oldquote:
        return ""
    else:
        if len(to) == 1:
            q = to[0]
        else:
            q = ""
            for word in to:
                q = q + word[0]
        return q


def show_subject(subject):
    if len(subject) > width - 8:
        msg = ""
        line = ""
        for word in subject.split(" "):
            if len(line + word) <= width - 4:
                line = line + word + " "
            else:
                msg = msg + line + "\n"
                line = word + " "
        msg = msg + line
        message_box(msg)


def calc_scrollbar_size(length):
    if length > 0:
        scrollbar_size = round((height - 6) * (height - 6) / length + 0.49)
        if scrollbar_size < 1:
            scrollbar_size = 1
    else:
        scrollbar_size = 1
    return scrollbar_size


def set_attr(s):
    if s == chr(15):
        stdscr.attrset(get_color("quote1"))
    elif s == chr(16):
        stdscr.attrset(get_color("quote2"))
    elif s == chr(17):
        stdscr.attrset(get_color("comment"))
    elif s == chr(18):
        stdscr.attrset(get_color("header"))
    elif s == chr(19):
        stdscr.attrset(get_color("origin"))
    else:
        stdscr.attrset(get_color("text"))


def get_msg(msgid):
    r = urllib.request.Request(nodes[node]["node"] + "u/m/" + msgid)
    with urllib.request.urlopen(r) as f:
        bundle = f.read().decode("utf-8").split("\n")
    for msg in bundle:
        if not msg:
            continue
        m = msg.split(":")
        msgid = m[0]
        if len(msgid) == 20 and m[1]:
            msgbody = base64.b64decode(m[1].encode("ascii")).decode("utf8").split("\n")
            if nodes[node]["to"]:
                carbonarea = api.get_carbonarea()
                if msgbody[5] in nodes[node]["to"] and msgid not in carbonarea:
                    pass
                    # add_to_carbonarea(msgid, msgbody)
            # save_message(msgid, msgbody)
    # TODO: Restore message body only w/o duplicates in echo index


def show_menu(title, items):
    h = len(items)
    w = 0 if not items else min(width - 3, max(map(lambda it: len(it), items)))
    e = "Esc - отмена"
    if w < len(title):
        w = len(title) + 2
    menu_win = curses.newwin(h + 2, w + 2,
                             int(height / 2 - h / 2 - 2),
                             int(width / 2 - w / 2 - 2))
    menu_win.attrset(get_color("border"))
    menu_win.border()
    color = get_color("border")
    menu_win.addstr(0, 1, "[", color)
    menu_win.addstr(0, 2 + len(title), "]", color)
    menu_win.addstr(h + 1, 1, "[", color)
    menu_win.addstr(h + 1, 2 + len(e), "]", color)

    color = get_color("titles")
    menu_win.addstr(0, 2, title, color)
    menu_win.addstr(h + 1, 2, e, color)
    y = 1
    while True:
        for i, item in enumerate(items, start=1):
            color = get_color("cursor" if i == y else "text")
            for x in range(1, w + 1):
                menu_win.addstr(i, x, " ", color)
            if len(item) < w - 2:
                menu_win.addstr(i, 1, item, color)
            else:
                menu_win.addstr(i, 1, item[:w], color)
        menu_win.refresh()
        key = stdscr.getch()
        if key in keys.r_up:
            if y > 1:
                y -= 1
            else:
                y = h
        elif key in keys.r_down:
            if y < h:
                y += 1
            else:
                y = 1
        elif key in keys.s_enter:
            return y  #
        elif key in keys.r_quit:
            return False  #


def open_link(link):
    # TODO: Support open ii:// link
    if not browser.open(link):
        message_box("Не удалось запустить Интернет-браузер")


def get_out(drafts=False):
    if drafts:
        return get_out_msgids(True)
    else:
        return get_out_msgids()


def echo_reader(echo, last, archive, favorites, out, carbonarea, drafts=False):
    global lasts, next_echoarea
    stdscr.clear()
    stdscr.attrset(get_color("border"))
    y = 0
    msgn = last
    if drafts:
        msgids = get_out_msgids(True)
    elif out:
        msgids = get_out_msgids()
    elif favorites and not carbonarea:
        msgids = api.get_favorites_list()
    elif carbonarea:
        msgids = api.get_carbonarea()
    else:
        msgids = api.get_echo_msgids(echo[0])
    if msgn > len(msgids) - 1:
        msgn = len(msgids) - 1
    if msgids:
        if drafts:
            msg, size = read_out_msg(msgids[msgn])
        elif out:
            msg, size = read_out_msg(msgids[msgn])
        else:
            msg, size = api.read_msg(msgids[msgn], echo[0])
            while msg[3] in twit or msg[5] in twit:
                msgn -= 1
                if msgn < 0:
                    next_echoarea = True
                    break
                msg, size = api.read_msg(msgids[msgn], echo[0])

    else:
        msg = ["", "", "", "", "", "", "", "", "Сообщение отсутствует в базе"]
        size = "0b"
    msgbody = body_render(msg[8:])
    scrollbar_size = calc_scrollbar_size(len(msgbody))
    go = True
    done = False
    repto = False
    stack = []
    while go:
        if msgids:
            draw_reader(msg[1], msgids[msgn], out)
            if width >= 80:
                msg_string = ("Сообщение " + str(msgn + 1) + " из " + str(len(msgids))
                              + " (" + str(len(msgids) - msgn - 1) + " осталось)")
            else:
                msg_string = (str(msgn + 1) + "/" + str(len(msgids))
                              + " [" + str(len(msgids) - msgn - 1) + "]")
            draw_status(len(version) + 2, msg_string)
            if drafts:
                dsc = "Черновики"
            elif out:
                dsc = "Исходящие"
            else:
                dsc = echo[1]
            if dsc and width >= 80:
                draw_title(0, width - 2 - len(dsc), dsc)
            color = get_color("text")
            if not out:
                try:
                    fmt = "%d.%m.%y %H:%M"
                    if width >= 80:
                        fmt = "%d %b %Y %H:%M UTC"
                    msgtime = time.strftime(fmt, time.gmtime(int(msg[2])))
                except ValueError:
                    msgtime = ""
                if width >= 80:
                    stdscr.addstr(1, 7, msg[3] + " (" + msg[4] + ")", color)
                else:
                    stdscr.addstr(1, 7, msg[3], color)
                stdscr.addstr(1, width - len(msgtime) - 1, msgtime, color)
            else:
                if len(nodes[node]["to"]) > 0:
                    stdscr.addstr(1, 7, nodes[node]["to"][0], color)
            stdscr.addstr(2, 7, msg[5], color)
            stdscr.addstr(3, 7, msg[6][:width - 8], color)
            draw_title(4, 0, size)
            tags = msg[0].split("/")
            if "repto" in tags and 36 + len(size) < width:
                repto = tags[tags.index("repto") + 1]
                draw_title(4, len(size) + 3, "Ответ на " + repto)
            else:
                repto = False
            for i in range(0, height - 6):
                stdscr.addstr(i + 5, 0, " " * width, 1)
                if i < len(msgbody) - 1:
                    if y + i < len(msgbody) and len(msgbody[y + i]) > 0:
                        set_attr(msgbody[y + i][0])
                        x = 0
                        for word in msgbody[y + i][1:].split(" "):
                            if is_url(word):
                                stdscr.attrset(get_color("url"))
                                stdscr.addstr(i + 5, x, word)
                                set_attr(msgbody[y + i][0])
                            else:
                                stdscr.addstr(i + 5, x, word)
                            x += len(word) + 1
            stdscr.attrset(get_color("scrollbar"))
            if len(msgbody) > height - 5:
                for i in range(5, height - 1):
                    stdscr.addstr(i, width - 1, "░")
                scrollbar_y = round(y * (height - 6) / len(msgbody) + 0.49)
                if scrollbar_y < 0:
                    scrollbar_y = 0
                elif scrollbar_y > height - 6 - scrollbar_size or y >= len(msgbody) - (height - 6):
                    scrollbar_y = height - 6 - scrollbar_size
                for i in range(scrollbar_y + 5, scrollbar_y + 5 + scrollbar_size):
                    if i < height - 1:
                        stdscr.addstr(i, width - 1, "█")
        else:
            draw_reader(echo[0], "", out)
        stdscr.attrset(get_color("border"))
        stdscr.refresh()
        key = stdscr.getch()
        if key == curses.KEY_RESIZE:
            y = 0
            get_term_size()
            if msgids:
                msgbody = body_render(msg[8:])
                scrollbar_size = calc_scrollbar_size(len(msgbody))
            stdscr.clear()
        elif key in keys.r_prev and msgn > 0:
            y = 0
            if msgids:
                msgn = msgn - 1
                stack.clear()
                if out:
                    msg, size = read_out_msg(msgids[msgn])
                else:
                    msg, size = api.read_msg(msgids[msgn], echo[0])
                tmp = msgn
                while msg[3] in twit or msg[5] in twit:
                    msgn -= 1
                    if msgn < 0:
                        msgn = tmp + 1
                        break
                    msg, size = api.read_msg(msgids[msgn], echo[0])
                msgbody = body_render(msg[8:])
                scrollbar_size = calc_scrollbar_size(len(msgbody))
        elif key in keys.r_next and msgn < len(msgids) - 1:
            y = 0
            if msgids:
                msgn = msgn + 1
                stack.clear()
                if out:
                    msg, size = read_out_msg(msgids[msgn])
                else:
                    msg, size = api.read_msg(msgids[msgn], echo[0])
                while msg[3] in twit or msg[5] in twit:
                    msgn += 1
                    if msgn >= len(msgids) or len(msgids) == 0:
                        go = False
                        next_echoarea = True
                        break
                    msg, size = api.read_msg(msgids[msgn], echo[0])
                msgbody = body_render(msg[8:])
                scrollbar_size = calc_scrollbar_size(len(msgbody))
        elif key in keys.r_next and (msgn == len(msgids) - 1 or len(msgids) == 0):
            go = False
            next_echoarea = True
        elif key in keys.r_prep and not echo[0] == "carbonarea" and not echo[0] == "favorites" and not out and repto:
            if repto in msgids:
                stack.append(msgn)
                msgn = msgids.index(repto)
                msg, size = api.read_msg(msgids[msgn], echo[0])
                msgbody = body_render(msg[8:])
                scrollbar_size = calc_scrollbar_size(len(msgbody))
        elif key in keys.r_nrep and not out and len(stack) > 0:
            msgn = stack.pop()
            msg, size = api.read_msg(msgids[msgn], echo[0])
            msgbody = body_render(msg[8:])
            scrollbar_size = calc_scrollbar_size(len(msgbody))
        elif key in keys.r_up and y > 0:
            if msgids:
                y = y - 1
        elif key in keys.r_ppage:
            if msgids:
                y = y - height + 6
                if y < 0:
                    y = 0
        elif key in keys.r_npage:
            if y < len(msgbody) - height + 5:
                if msgids and len(msgbody) > height - 5:
                    y = y + height - 6
        elif key in keys.r_home:
            if msgids:
                y = 0
        elif key in keys.r_mend:
            if msgids and len(msgbody) > height - 5:
                y = len(msgbody) - height + 5
        elif key in keys.r_ukeys:
            if len(msgids) == 0 or y >= len(msgbody) - height + 5:
                y = 0
                if msgn == len(msgids) - 1 or len(msgids) == 0:
                    next_echoarea = True
                    go = False
                else:
                    msgn = msgn + 1
                    stack.clear()
                    if out:
                        msg, size = read_out_msg(msgids[msgn])
                    else:
                        msg, size = api.read_msg(msgids[msgn], echo[0])
                    msgbody = body_render(msg[8:])
                    scrollbar_size = calc_scrollbar_size(len(msgbody))
            else:
                if msgids and len(msgbody) > height - 5:
                    y = y + height - 6
        elif key in keys.r_down:
            if msgids:
                if y + height - 5 < len(msgbody):
                    y = y + 1
        elif key in keys.r_begin:
            if msgids:
                y = 0
                msgn = 0
                stack.clear()
                if out:
                    msg, size = read_out_msg(msgids[msgn])
                else:
                    msg, size = api.read_msg(msgids[msgn], echo[0])
                msgbody = body_render(msg[8:])
                scrollbar_size = calc_scrollbar_size(len(msgbody))
        elif key in keys.r_end:
            if msgids:
                y = 0
                msgn = len(msgids) - 1
                stack.clear()
                if out:
                    msg, size = read_out_msg(msgids[msgn])
                else:
                    msg, size = api.read_msg(msgids[msgn], echo[0])
                msgbody = body_render(msg[8:])
                scrollbar_size = calc_scrollbar_size(len(msgbody))
        elif key in keys.r_ins and not archive and not out:
            if not favorites:
                t = open("template.txt", "r")
                f = open("temp", "w")
                f.write(echo[0] + "\n")
                f.write("All\n")
                f.write("No subject\n\n")
                f.write(t.read())
                f.close()
                t.close()
                call_editor()
                stdscr.clear()
        elif key in keys.r_save and not out:
            save_message_to_file(msgids[msgn], echo[0])
        elif key in keys.r_favorites and not out:
            saved = api.save_to_favorites(msgids[msgn], msg)
            draw_message_box("Подождите", False)
            get_counts(False, True)
            if saved:
                message_box("Сообщение добавлено в избранные")
            else:
                message_box("Сообщение уже есть в избранных")
        elif key in keys.r_quote and not archive and not out:
            if msgids:
                t = open("template.txt", "r")
                f = open("temp", "w")
                f.write(msgids[msgn] + "\n")
                f.write(msg[1] + "\n")
                f.write(msg[3] + "\n")
                to = msg[3].split(" ")
                q = quote(to)
                if not msg[6].startswith("Re:"):
                    f.write("Re: " + msg[6] + "\n")
                else:
                    f.write(msg[6] + "\n")
                for line in msg[8:]:
                    if line.startswith("+++") or line.strip() == "":
                        continue  # skip sign and empty lines
                    qq = quote_template.match(line)
                    if qq:
                        quoter = ">"
                        if not line[qq.span()[1]] == " ":
                            quoter += " "
                        f.write("\n" + line[:qq.span()[1]]
                                + quoter
                                + line[qq.span()[1]:])
                    else:
                        f.write("\n" + q + "> " + line)
                f.write(t.read())
                f.close()
                t.close()
                call_editor()
        elif key in keys.r_subj:
            show_subject(msg[6])
        elif key in keys.r_info and not out and width < 80:
            message_box("id  : " + msgids[msgn] + "\naddr: " + msg[4])
        elif key in keys.o_edit and out:
            if msgids[msgn].endswith(".out") or msgids[msgn].endswith(".draft"):
                copyfile("out/" + nodes[node]["nodename"] + "/" + msgids[msgn], "temp")
                call_editor(msgids[msgn])
                msgids = get_out(drafts=drafts)
                if msgn > len(msgids) - 1:
                    msgn = len(msgids) - 1
                if msgids:
                    msg, size = read_out_msg(msgids[msgn])
                    msgbody = body_render(msg[8:])
                else:
                    go = False
                scrollbar_size = calc_scrollbar_size(len(msgbody))
                stdscr.clear()
            else:
                message_box("Сообщение уже отправлено")
                stdscr.clear()
        elif key in keys.f_delete and favorites and not carbonarea:
            if msgids:
                api.remove_from_favorites(msgids[msgn])
                draw_message_box("Подождите", False)
                get_counts(False, True)
                msgids = api.get_echo_msgids(echo[0])
                if msgids:
                    if msgn >= len(msgids):
                        msgn = len(msgids) - 1
                    msg, size = api.read_msg(msgids[msgn], echo[0])
                    msgbody = body_render(msg[8:])
                    scrollbar_size = calc_scrollbar_size(len(msgbody))
                else:
                    msgbody = []
                stdscr.clear()
        elif key in keys.r_getmsg and size == "0b":
            try:
                get_msg(msgids[msgn])
                draw_message_box("Подождите", False)
                get_counts(True, False)
                stdscr.clear()
                msg, size = api.read_msg(msgids[msgn], echo[0])
                msgbody = body_render(msg[8:])
                scrollbar_size = calc_scrollbar_size(len(msgbody))
            except Exception as ex:
                message_box("Не удалось определить msgid. " + str(ex))
                stdscr.clear()
        elif key in keys.r_links:
            # TODO: Find and open ii:// links
            results = url_template.findall("\n".join(msg[8:]))
            links = [it[0] for it in results]
            if len(links) == 1:
                open_link(links[0])
            elif links:
                i = show_menu("Выберите ссылку", links)
                if i:
                    open_link(links[i - 1])
            stdscr.clear()
        elif key in keys.r_to_out and drafts:
            node_dir = "out/" + nodes[node]["nodename"]
            os.rename(node_dir + "/" + msgids[msgn],
                      node_dir + "/" + msgids[msgn].replace(".draft", ".out"))
            msgids = get_out(drafts=drafts)
            if msgn > len(msgids) - 1:
                msgn = len(msgids) - 1
            if msgids:
                msg, size = read_out_msg(msgids[msgn])
                msgbody = body_render(msg[8:])
            else:
                go = False
        elif key in keys.r_to_drafts and out and not drafts and msgids[msgn].endswith(".out"):
            node_dir = "out/" + nodes[node]["nodename"]
            os.rename(node_dir + "/" + msgids[msgn],
                      node_dir + "/" + msgids[msgn].replace(".out", ".draft"))
            msgids = get_out(drafts=drafts)
            if msgn > len(msgids) - 1:
                msgn = len(msgids) - 1
            if msgids:
                msg, size = read_out_msg(msgids[msgn])
                msgbody = body_render(msg[8:])
            else:
                go = False
        elif key in keys.r_list and not out and not drafts:
            if db == "txt":
                message_box("Функция не поддерживается текстовой базой.")
            else:
                selected_msgn = show_msg_list_screen(echo, msgn)
                if selected_msgn > -1:
                    y = 0
                    msgn = selected_msgn
                    stack.clear()
                    msg, size = api.read_msg(msgids[msgn], echo[0])
                    msgbody = body_render(msg[8:])
                    scrollbar_size = calc_scrollbar_size(len(msgbody))
        elif key in keys.r_quit:
            go = False
            next_echoarea = False
        elif key in keys.g_quit:
            go = False
            done = True
    lasts[echo[0]] = msgn
    with open("lasts.lst", "wb") as f:
        pickle.dump(lasts, f)
    stdscr.clear()
    return done


def is_url(word: str):
    return (word.startswith("http://")
            or word.startswith("https://")
            or word.startswith("ftp://")
            or word.startswith("ii://"))


# noinspection PyUnusedLocal
def draw_msg_list(echo, lst, msgn):
    stdscr.clear()
    color = get_color("border")
    stdscr.insstr(0, 0, "─" * width, color)
    if width >= 80:
        draw_title(0, 0, "Список сообщений в конференции " + echo)
    else:
        draw_title(0, 0, echo)


def show_msg_list_screen(echoarea, msgn):
    lst = api.get_msg_list_data(echoarea[0])
    draw_msg_list(echoarea[0], lst, msgn)
    echo_length = len(lst)
    if echo_length <= height - 1:
        start = 0
        end = echo_length
    elif msgn + height - 1 < echo_length:
        start = msgn
        end = msgn + height - 1
    else:
        start = echo_length - height + 1
        end = start + height - 1
    y = msgn - start
    while True:
        n = 1
        for i in range(start, end):
            if i == y + start:
                color = get_color("cursor")
            else:
                color = get_color("text")
            draw_cursor(n - 1, color)
            stdscr.addstr(n, 0, lst[i][1], color)
            stdscr.addstr(n, 16, lst[i][2][:width - 26], color)
            stdscr.insstr(n, width - 10, lst[i][3], color)
            n += 1
        key = stdscr.getch()
        if key in keys.s_up:
            y = y - 1
            if start > 0 and y + start < start:
                start -= 1
                end -= 1
            if y == -1:
                y = 0
        elif key in keys.s_down:
            y = y + 1
            if y + start + 1 > end and y + start < echo_length:
                start += 1
                end += 1
            if y > height - 2:
                y = height - 2
            y = min(y, echo_length - 1)
        elif key in keys.s_ppage:
            if y == 0:
                start = max(0, start - height + 1)
                end = min(echo_length, start + height - 1)
            y = 0
        elif key in keys.s_npage:
            if y == height - 2:
                start = start + height - 1
                if start > echo_length - height + 1:
                    start = echo_length - height + 1
                end = start + height - 1
            y = min(echo_length - 1, height - 2)
        elif key in keys.s_home:
            y = 0
            start = 0
            end = min(echo_length, height - 1)
        elif key in keys.s_end:
            y = min(echo_length - 1, height - 2)
            start = max(0, echo_length - height + 1)
            end = min(echo_length, start + height - 1)
        elif key in keys.s_enter:
            return y + start  #
        elif key in keys.r_quit:
            return -1  #


if sys.version_info >= (3, 11):
    loc = locale.getlocale()
else:
    # noinspection PyDeprecation
    loc = locale.getdefaultlocale()
locale.setlocale(locale.LC_ALL, loc[0] + "." + loc[1])

check_config()
reset_config()
load_config()
if db == "txt":
    import api.txt as api
elif db == "aio":
    import api.aio as api
elif db == "ait":
    import api.ait as api
elif db == "sqlite":
    import api.sqlite as api
else:
    raise Exception("Unsupported DB API :: " + db)
check_directories()
stdscr = curses.initscr()
if sys.version_info >= (3, 10):
    can_change_color = (curses.has_extended_color_support()
                        and curses.can_change_color())
else:
    can_change_color = ("256" in os.environ.get("TERM", "linux")
                        and curses.can_change_color())
try:
    curses.start_color()
    curses.use_default_colors()
    curses.noecho()
    curses.set_escdelay(50)  # ms
    curses.curs_set(False)
    stdscr.keypad(True)
    get_term_size()
    try:
        load_colors(color_theme)
    except ValueError as err:
        load_colors("default")
        stdscr.refresh()
        message_box("Цветовая схема " + color_theme + " не установлена.\n"
                    + str(err) + "\nБудет использована схема по-умолчанию.")
        color_theme = "default"
    stdscr.bkgd(" ", get_color("text"))

    if show_splash:
        splash_screen()
    draw_message_box("Подождите", False)
    get_counts()
    stdscr.clear()
    show_echo_selector_screen()
finally:
    curses.echo()
    curses.curs_set(True)
    stdscr.keypad(False)
    curses.endwin()
