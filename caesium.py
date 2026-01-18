#!/usr/bin/env python3
# coding=utf-8
import base64
import codecs
import curses
import hashlib
import locale
import os
import pickle
import subprocess
import sys
from datetime import datetime
from shutil import copyfile
from typing import List

from core import parser, client, config, utils
from core.config import get_color

# TODO: Add http/https/socks proxy support
# import socket
# import socks
# socks.set_default_proxy(socks.SOCKS5, '127.0.0.1', 8081)
# socket.socket = socks.socksocket

lasts = {}
if os.path.exists("lasts.lst"):
    with open("lasts.lst", "rb") as f_lasts:
        lasts = pickle.load(f_lasts)
blacklist = []
if os.path.exists("blacklist.txt"):
    with open("blacklist.txt", "r") as bl:
        blacklist = list(filter(None, map(lambda it: it.strip(),
                                          bl.readlines())))
counts = []
counts_rescan = True
echo_counts = {}
next_echoarea = False
node = 0
cfg = config.Config()

version = "Caesium/0.6 │"
client.USER_AGENT = "Caesium/0.6"

splash = ["▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀",
          "████████ ████████ ████████ ████████ ███ ███  ███ ██████████",
          "███           ███ ███  ███ ███          ███  ███ ███ ██ ███",
          "███      ████████ ████████ ████████ ███ ███  ███ ███ ██ ███",
          "███      ███  ███ ███           ███ ███ ███  ███ ███ ██ ███",
          "████████ ████████ ████████ ████████ ███ ████████ ███ ██ ███",
          "▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄",
          "           ncurses ii/idec client        v0.6",
          "           Andrew Lobanov             04.01.2026"]


def reset_config():
    global node
    node = 0
    cfg.reset()


def check_directories(storage_api):
    if not os.path.exists("out"):
        os.mkdir("out")
    for n in cfg.nodes:
        if not os.path.exists("out/" + n.nodename):
            os.mkdir("out/" + n.nodename)
    storage_api.init()


#
# Взаимодействие с нодой
#
def save_out(draft=False):
    with codecs.open("temp", "r", "utf-8") as f:
        new = f.read().strip().replace("\r", "").split("\n")
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
        ext = ".draft" if draft else ".out"
        with codecs.open(outcount() + ext, "w", "utf-8") as f:
            f.write("\n".join(buf))
        os.remove("temp")


def resave_out(filename, draft=False):
    with codecs.open("temp", "r", "utf-8") as f:
        new = f.read().strip().split("\n")
    if len(new) <= 1:
        os.remove("temp")
    else:
        out_dir = "out/" + cfg.nodes[node].nodename + "/"
        if draft:
            filename = filename.replace(".out", ".draft")
        with codecs.open(out_dir + filename, "w", "utf-8") as f:
            f.write("\n".join(new))
        os.remove("temp")


def outcount():
    outpath = "out/" + cfg.nodes[node].nodename
    i = str(len([x for x in os.listdir(outpath)
                 if not x.endswith(".toss")]) + 1)
    return outpath + "/%s" % i.zfill(5)


def get_out_length(drafts=False):
    node_dir = "out/" + cfg.nodes[node].nodename
    if drafts:
        return len([f for f in sorted(os.listdir(node_dir))
                    if f.endswith(".draft")]) - 1
    else:
        return len([f for f in sorted(os.listdir(node_dir))
                    if f.endswith(".out") or f.endswith(".outmsg")]) - 1


def make_toss(node_):  # type: (config.Node) -> None
    node_dir = "out/" + node_.nodename
    lst = [x for x in os.listdir(node_dir)
           if x.endswith(".out")]
    for msg in lst:
        with codecs.open(node_dir + "/%s" % msg, "r", "utf-8") as f:
            text_raw = f.read()
        text_b64 = base64.b64encode(text_raw.encode("utf-8")).decode("utf-8")
        with codecs.open(node_dir + "/%s.toss" % msg, "w", "utf-8") as f:
            f.write(text_b64)
        os.rename(node_dir + "/%s" % msg,
                  node_dir + "/%s%s" % (msg, "msg"))


def send_mail(node_):  # type: (config.Node) -> None
    lst = [x for x in sorted(os.listdir("out/" + node_.nodename))
           if x.endswith(".toss")]
    total = str(len(lst))
    try:
        node_dir = "out/" + node_.nodename
        for n, msg in enumerate(lst, start=1):
            print("\rОтправка сообщения: " + str(n) + "/" + total, end="")
            msg_toss = node_dir + "/%s" % msg
            with codecs.open(msg_toss, "r", "utf-8") as f:
                text = f.read()
            #
            result = client.send_msg(node_.url, node_.auth, text)
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


def debundle(bundle):
    messages = []
    for msg in filter(None, bundle):
        m = msg.split(":")
        msgid = m[0]
        if len(msgid) == 20 and m[1]:
            msgbody = base64.b64decode(m[1].encode("ascii")).decode("utf8").split("\n")
            messages.append([msgid, msgbody])
    if messages:
        api.save_message(messages, node, cfg.nodes[node].to)


def get_mail(node_):  # type: (config.Node) -> None
    fetch_msg_list = []
    print("Получение индекса от ноды...")
    echoareas = list(map(lambda e: e.name, filter(lambda e: e.sync,
                                                  node_.echoareas)))
    remote_msg_list = client.get_msg_list(node_.url, echoareas)
    print("Построение разностного индекса...")
    local_index = None
    for line in remote_msg_list:
        if parser.echo_template.match(line):
            local_index = api.get_echo_msgids(line)
        elif len(line) == 20 and line not in local_index and line not in blacklist:
            fetch_msg_list.append(line)
    if fetch_msg_list:
        total = str(len(fetch_msg_list))
        count = 0
        for get_list in utils.separate(fetch_msg_list):
            count += len(get_list)
            print("\rПолучение сообщений: " + str(count) + "/" + total, end="")
            debundle(client.get_bundle(node_.url, "/".join(get_list)))
    else:
        print("Новых сообщений не обнаружено.", end="")
    print()


def fetch_mail(node_):  # type: (config.Node) -> None
    print("Работа с " + node_.url)
    try:
        if node_.auth:
            make_toss(node_)
            send_mail(node_)
        get_mail(node_)
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
WIDTH = 0
HEIGHT = 0


def splash_screen():
    stdscr.clear()
    x = int((WIDTH - len(splash[1])) / 2) - 1
    y = int((HEIGHT - len(splash)) / 2)
    i = 0
    for line in splash:
        stdscr.addstr(y + i, x, line, get_color("text"))
        i = i + 1
    stdscr.refresh()
    curses.napms(2000)
    stdscr.clear()


def get_term_size():
    global WIDTH, HEIGHT
    HEIGHT, WIDTH = stdscr.getmaxyx()


def draw_title(y, x, title):
    x = max(0, x)
    if (x + len(title) + 2) > WIDTH:
        title = title[:WIDTH - x - 2 - 3] + '...'
    #
    color = get_color("border")
    stdscr.addstr(y, x, "[", color)
    stdscr.addstr(y, x + 1 + len(title), "]", color)
    color = get_color("titles")
    stdscr.addstr(y, x + 1, title, color)


def draw_status(x, title):
    color = get_color("statusline")
    stdscr.addstr(HEIGHT - 1, x, title, color)


def draw_cursor(y, color):
    stdscr.insstr(y + 1, 0, " " * WIDTH, color)


def current_time():
    draw_status(WIDTH - 8, "│ " + datetime.now().strftime("%H:%M"))


def get_counts(new=False):
    for echo in cfg.nodes[node].echoareas:  # type: config.Echo
        if not new:
            if echo.name not in echo_counts:
                echo_counts[echo.name] = api.get_echo_length(echo.name)
        else:
            echo_counts[echo.name] = api.get_echo_length(echo.name)
    for echo in cfg.nodes[node].archive:  # type: config.Echo
        if echo.name not in echo_counts:
            echo_counts[echo.name] = api.get_echo_length(echo.name)
    echo_counts[config.ECHO_CARBON.name] = len(api.get_carbonarea())
    echo_counts[config.ECHO_FAVORITES.name] = len(api.get_favorites_list())


def rescan_counts(echoareas):
    counts_ = []
    for echo in echoareas:
        echocount = echo_counts[echo.name]
        if echo.name in lasts:
            last = echocount - lasts[echo.name]
            if echocount == 0 and lasts[echo.name] == 0:
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
    stdscr.insstr(0, 0, "─" * WIDTH, color)
    color = get_color("statusline")
    stdscr.insstr(HEIGHT - 1, 0, " " * WIDTH, color)
    if archive:
        echoareas = cfg.nodes[node].archive
        draw_title(0, 0, "Архив")
    else:
        echoareas = cfg.nodes[node].echoareas
        draw_title(0, 0, "Конференция")
    draw_status(1, version)
    draw_status(len(version) + 2, cfg.nodes[node].nodename)
    for echo in echoareas:
        desc_len = len(echo.desc)
        if desc_len > m:
            m = desc_len
        if m > WIDTH - 38:
            m = WIDTH - 38
        dsc_lens.append(desc_len)
    y = 0
    count = "Сообщений"
    unread = "Не прочитано"
    description = "Описание"
    if WIDTH < 80 or m == 0:
        m = len(unread) - 7
        hidedsc = True
    draw_title(0, WIDTH + 2 - m - len(count) - len(unread) - 1, count)
    draw_title(0, WIDTH - 8 - m - 1, unread)
    if not hidedsc:
        draw_title(0, WIDTH - len(description) - 2, description)
    for echo in echoareas:
        if y - start < HEIGHT - 2:
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
                if echo.name in lasts:
                    last = lasts[echo.name]
                else:
                    last = -1
                if last < echo_length - 1 or last == -1 and echo_length == 1:
                    stdscr.addstr(y + 1 - start, 0, "+")
                stdscr.addstr(y + 1 - start, 2, echo.name)
                if WIDTH >= 80:
                    if WIDTH - 38 >= len(echo.desc):
                        stdscr.addstr(y + 1 - start, WIDTH - 1 - dsc_lens[y], echo.desc, color)
                    else:
                        cut_index = WIDTH - 38 - len(echo.desc)
                        stdscr.addstr(y + 1 - start, WIDTH - 1 - len(echo.desc[:cut_index]), echo.desc[:cut_index])
                stdscr.addstr(y + 1 - start, WIDTH - 10 - m - len(counts[y][0]), counts[y][0])
                stdscr.addstr(y + 1 - start, WIDTH - 2 - m - len(counts[y][1]), counts[y][1])
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
    terminate_curses()
    p = subprocess.Popen(cfg.editor + " " + config.CONFIG_FILEPATH, shell=True)
    p.wait()
    reset_config()
    cfg.load()
    stdscr = curses.initscr()
    initialize_curses()


def show_echo_selector_screen():
    global echo_cursor, archive_cursor, counts, counts_rescan, next_echoarea, node, stdscr
    archive = False
    echoareas = cfg.nodes[node].echoareas
    go = True
    start = 0
    if archive:
        cursor = echo_cursor
    else:
        cursor = archive_cursor

    def toggle_archive():
        global echo_cursor, archive_cursor, counts_rescan
        nonlocal cursor, echoareas, archive
        archive = not archive
        if not archive:
            archive_cursor = cursor
            cursor = echo_cursor
            echoareas = cfg.nodes[node].echoareas
        else:
            echo_cursor = cursor
            cursor = archive_cursor
            echoareas = cfg.nodes[node].archive
        stdscr.clear()
        counts_rescan = True

    def ensure_cursor_visible():
        nonlocal start
        if cursor - start > HEIGHT - 3:
            start = cursor - HEIGHT + 3
        elif cursor - start < 0:
            start = cursor

    while go:
        draw_echo_selector(start, cursor, archive)
        key = stdscr.getch()
        if key == curses.KEY_RESIZE:
            get_term_size()
            if cursor >= HEIGHT - 2:
                start = cursor - HEIGHT + 3
            if cursor - start <= 0:
                start = cursor
            if start > 0 and HEIGHT - 2 > len(echoareas):
                start = 0
            stdscr.clear()
        elif key in keys.s_up and cursor > 0:
            cursor = cursor - 1
            if cursor - start < 0 < start:
                start = start - 1
        elif key in keys.s_down and cursor < len(echoareas) - 1:
            cursor = cursor + 1
            if cursor - start > HEIGHT - 3 and start < len(echoareas) - HEIGHT + 2:
                start = start + 1
        elif key in keys.s_ppage:
            cursor = cursor - HEIGHT + 2
            if cursor < 0:
                cursor = 0
            if cursor - start < 0 < start:
                start = start - HEIGHT + 2
            if start < 0:
                start = 0
        elif key in keys.s_npage:
            cursor = cursor + HEIGHT - 2
            if cursor >= len(echoareas):
                cursor = len(echoareas) - 1
            if cursor - start > HEIGHT - 3:
                start = start + HEIGHT - 2
                if start > len(echoareas) - HEIGHT + 2:
                    start = len(echoareas) - HEIGHT + 2
        elif key in keys.s_home:
            cursor = 0
            start = 0
        elif key in keys.s_end:
            cursor = len(echoareas) - 1
            if len(echoareas) >= HEIGHT - 2:
                start = len(echoareas) - HEIGHT + 2
        elif key in keys.s_get:
            terminate_curses()
            os.system('cls' if os.name == 'nt' else 'clear')
            fetch_mail(cfg.nodes[node])
            stdscr = curses.initscr()
            initialize_curses()
            draw_message_box("Подождите", False)
            get_counts(True)
            stdscr.clear()
            counts = rescan_counts(echoareas)
            cursor = find_new(0)
            if cursor >= HEIGHT - 2:
                start = cursor - HEIGHT + 3
            if cursor - start <= 0:
                start = cursor
        elif key in keys.s_archive and len(cfg.nodes[node].archive) > 0:
            toggle_archive()
            ensure_cursor_visible()
        elif key in keys.s_enter:
            draw_message_box("Подождите", False)
            if echoareas[cursor].name in lasts:
                last = lasts[echoareas[cursor].name]
            else:
                last = 0
            if cursor == 0:
                echo_length = len(api.get_favorites_list())
            elif cursor == 1:
                echo_length = len(api.get_carbonarea())
            else:
                echo_length = api.get_echo_length(echoareas[cursor].name)
            if 0 < last < echo_length:
                last = last + 1
            if last >= echo_length:
                last = echo_length
            go = not echo_reader(echoareas[cursor], last, archive)
            counts_rescan = True
            if next_echoarea and isinstance(next_echoarea, bool):
                counts = rescan_counts(echoareas)
                cursor = find_new(cursor)
                ensure_cursor_visible()
                next_echoarea = False
            elif next_echoarea and isinstance(next_echoarea, str):
                cur_node = cfg.nodes[node]
                if ((not archive and next_echoarea in cur_node.archive)
                        or (archive and (next_echoarea in cur_node.echoareas
                                         or next_echoarea in cur_node.stat))):
                    toggle_archive()
                # noinspection PyTypeChecker
                cursor = echoareas.index(next_echoarea) if next_echoarea in echoareas else 0
                ensure_cursor_visible()
                next_echoarea = False

        elif key in keys.s_out:
            out_length = get_out_length(drafts=False)
            if out_length > -1:
                go = not echo_reader(config.ECHO_OUT, out_length, archive)
        elif key in keys.s_drafts:
            out_length = get_out_length(drafts=True)
            if out_length > -1:
                go = not echo_reader(config.ECHO_DRAFTS, out_length, archive)
        elif key in keys.s_nnode:
            archive = False
            node = node + 1
            if node == len(cfg.nodes):
                node = 0
            echoareas = cfg.nodes[node].echoareas
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
                node = len(cfg.nodes) - 1
            echoareas = cfg.nodes[node].echoareas
            draw_message_box("Подождите", False)
            get_counts()
            stdscr.clear()
            counts_rescan = True
            cursor = 0
            start = 0
        elif key in keys.s_config:
            edit_config()
            config.load_colors(cfg.theme)
            get_counts()
            stdscr.clear()
            counts_rescan = True
            node = 0
            archive = False
            echoareas = cfg.nodes[node].echoareas
            cursor = 0
        elif key in keys.g_quit:
            go = False
    if archive:
        archive_cursor = cursor
    else:
        echo_cursor = cursor


def read_out_msg(msgid, node_):  # type: (str, config.Node) -> (List[str], int)
    node_dir = "out/" + node_.nodename
    with open(node_dir + "/" + msgid, "r") as f:
        temp = f.read().splitlines()
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
    return msg, size


def render_body(scr, tokens, scroll):
    tnum, offset = parser.find_visible_token(tokens, scroll)
    line_num = tokens[tnum].line_num
    for y in range(5, HEIGHT - 1):
        scr.addstr(y, 0, " " * WIDTH, 1)
    y, x = (5, 0)
    for token in tokens[tnum:]:
        if token.line_num > line_num:
            line_num = token.line_num
            y, x = (y + 1, 0)
        if y >= HEIGHT - 1:
            break  # tokens
        y, x = render_token(scr, token, y, x, offset)
        offset = 0  # required in the first partial multiline token only


def render_token(scr, token: parser.Token, y, x, offset):
    for i, line in enumerate(token.render[offset:]):
        if y + i >= HEIGHT - 1:
            return y + i, x  #
        attr = get_color("text")
        if token.type in (parser.TT.CODE, parser.TT.COMMENT, parser.TT.HEADER,
                          parser.TT.ORIGIN, parser.TT.QUOTE1, parser.TT.QUOTE2,
                          parser.TT.URL):
            attr = get_color(token.type.name.lower())
        if line:
            scr.addstr(y + i, x, line, attr)

        if len(token.render) > 1 and i + offset < len(token.render) - 1:
            x = 0  # new line in multiline token -- carriage return
        else:
            x += len(line)  # last/single line -- move caret in line
    return y + (len(token.render) - 1) - offset, x  #


def draw_reader(echo: str, msgid, out):
    color = get_color("border")
    stdscr.insstr(0, 0, "─" * WIDTH, color)
    stdscr.insstr(4, 0, "─" * WIDTH, color)
    color = get_color("statusline")
    stdscr.insstr(HEIGHT - 1, 0, " " * WIDTH, color)
    if out:
        draw_title(0, 0, echo)
        if msgid.endswith(".out"):
            ns = "не отправлено"
            draw_title(4, WIDTH - len(ns) - 2, ns)
    else:
        if WIDTH >= 80:
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


def draw_scrollbar(scr, body_height, thumb_size, scroll_view, y):
    scr.attrset(get_color("scrollbar"))
    for i in range(5, HEIGHT - 1):
        scr.addstr(i, WIDTH - 1, "░")
    thumb_y = utils.scroll_thumb_pos(body_height, y, scroll_view, thumb_size)
    for i in range(thumb_y + 5, thumb_y + 5 + thumb_size):
        if i < HEIGHT - 1:
            scr.addstr(i, WIDTH - 1, "█")


def call_editor(out=''):
    global stdscr
    terminate_curses()
    h = hashlib.sha1(str.encode(open("temp", "r", ).read())).hexdigest()
    p = subprocess.Popen(cfg.editor + " ./temp", shell=True)
    p.wait()
    stdscr = curses.initscr()
    initialize_curses()
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
                        os.remove("out/" + cfg.nodes[node].nodename + "/" + out)
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
                        os.remove("out/" + cfg.nodes[node].nodename + "/" + out)
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
                               int(HEIGHT / 2 - 2),
                               int(WIDTH / 2 - maxlen / 2 - 2))
    else:
        msgwin = curses.newwin(len(msg) + 2, maxlen + 2,
                               int(HEIGHT / 2 - 2),
                               int(WIDTH / 2 - maxlen / 2 - 2))
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
    with open(msgid + ".txt", "w") as f:
        f.write("== " + msg[1] + " ==================== " + str(msgid) + "\n")
        f.write("От:   " + msg[3] + " (" + msg[4] + ")\n")
        f.write("Кому: " + msg[5] + "\n")
        f.write("Тема: " + msg[6] + "\n")
        f.write("\n".join(msg[7:]))
    message_box("Сообщение сохранено в файл\n" + str(msgid) + ".txt")


def get_out_msgids(drafts=False):
    msgids = []
    node_dir = "out/" + cfg.nodes[node].nodename
    if os.path.exists(node_dir):
        if drafts:
            msgids = [f for f in sorted(os.listdir(node_dir))
                      if f.endswith(".draft")]
        else:
            msgids = [f for f in sorted(os.listdir(node_dir))
                      if f.endswith(".out") or f.endswith(".outmsg")]
    return msgids


def quote_msg(msgid, msg):
    with open("template.txt", "r") as t:
        with open("temp", "w") as f:
            f.write(msgid + "\n")
            f.write(msg[1] + "\n")
            f.write(msg[3] + "\n")
            subj = msg[6]
            if not msg[6].startswith("Re:"):
                subj = "Re: " + subj
            f.write(subj + "\n")
            #
            if cfg.oldquote:
                author = ""
            elif " " not in msg[3]:
                author = msg[3]
            else:
                author = "".join(map(lambda word: word[0], msg[3].split(" ")))
            for line in msg[8:]:
                if line.startswith("+++") or not line.strip():
                    continue  # skip sign and empty lines
                qq = parser.quote_template.match(line)
                if qq:
                    quoter = ">"
                    if line[qq.span()[1]] != " ":
                        quoter += " "
                    f.write("\n" + line[:qq.span()[1]]
                            + quoter
                            + line[qq.span()[1]:])
                else:
                    f.write("\n" + author + "> " + line)
            f.write(t.read())


def show_subject(subject):
    if len(subject) > WIDTH - 8:
        msg = ""
        line = ""
        for word in subject.split(" "):
            if len(line + word) <= WIDTH - 4:
                line = line + word + " "
            else:
                msg = msg + line + "\n"
                line = word + " "
        msg = msg + line
        message_box(msg)


def get_msg(msgid):
    node_ = cfg.nodes[node]
    bundle = client.get_bundle(node_.url, msgid)
    for msg in filter(None, bundle):
        m = msg.split(":")
        msgid = m[0]
        if len(msgid) == 20 and m[1]:
            msgbody = base64.b64decode(m[1].encode("ascii")).decode("utf8").split("\n")
            if node_.to:
                carbonarea = api.get_carbonarea()
                if msgbody[5] in node_.to and msgid not in carbonarea:
                    api.add_to_carbonarea(msgid, msgbody)
            api.save_message([(msgid, msgbody)], node_, node_.to)


def show_menu(title, items):
    h = len(items)
    w = 0 if not items else min(WIDTH - 3, max(map(lambda it: len(it), items)))
    e = "Esc - отмена"
    if w < len(title) + 2:
        w = len(title) + 2
    menu_win = curses.newwin(h + 2, w + 2,
                             int(HEIGHT / 2 - h / 2 - 2),
                             int(WIDTH / 2 - w / 2 - 2))
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
            menu_win.addstr(i, 1, " " * w, color)
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


def echo_reader(echo: config.Echo, msgn, archive):
    global next_echoarea
    stdscr.clear()
    stdscr.attrset(get_color("border"))
    y = 0
    out = (echo in (config.ECHO_OUT, config.ECHO_DRAFTS))
    drafts = (echo == config.ECHO_DRAFTS)
    favorites = (echo == config.ECHO_FAVORITES)
    carbonarea = (echo == config.ECHO_CARBON)
    if out:
        msgids = get_out_msgids(drafts)
    elif favorites:
        msgids = api.get_favorites_list()
    elif carbonarea:
        msgids = api.get_carbonarea()
    else:
        msgids = api.get_echo_msgids(echo.name)
    msgn = min(msgn, len(msgids) - 1)
    cur_node = cfg.nodes[node]  # type: config.Node
    scroll_view = HEIGHT - 5 - 1  # screen height - header - status line
    msg = ["", "", "", "", "", "", "", "", "Сообщение отсутствует в базе"]
    size = 0
    go = True
    done = False
    repto = False
    stack = []
    msgid = None

    def read_cur_msg():  # type: () -> (List[str], int)
        if out:
            return read_out_msg(msgids[msgn], cur_node)
        else:
            return api.read_msg(msgids[msgn], echo.name)

    def read_msg_skip_twit(increment):
        nonlocal msg, msgn, size
        msg, size = read_cur_msg()
        while msg[3] in cfg.twit or msg[5] in cfg.twit:
            msgn += increment
            if msgn < 0 or len(msgids) <= msgn:
                break
            msg, size = api.read_msg(msgids[msgn], echo.name)

    def prerender(msgbody):
        tokens = parser.tokenize(msgbody)
        b_height = parser.prerender(tokens, WIDTH, scroll_view)
        thumb_size = utils.scroll_thumb_size(b_height, scroll_view)
        return tokens, b_height, thumb_size

    def prerender_msg_or_quit():
        nonlocal msgn, msg, size, go, body_tokens, body_height, scroll_thumb_size
        if msgids:
            msgn = min(msgn, len(msgids) - 1)
            msg, size = read_cur_msg()
            body_tokens, body_height, scroll_thumb_size = prerender(msg[8:])
        else:
            go = False

    def open_link(link):  # type: (str) -> None
        nonlocal msgid, msgn, msg, size, go
        nonlocal body_tokens, body_height, scroll_thumb_size
        global next_echoarea
        if not link.startswith("ii://"):
            if not cfg.browser.open(link):
                message_box("Не удалось запустить Интернет-браузер")
        elif parser.echo_template.match(link[5:]):  # echoarea
            if echo.name == link[5:]:
                message_box("Конференция уже открыта")
            elif (link[5:] in cur_node.echoareas
                  or link[5:] in cur_node.archive
                  or link[5:] in cur_node.stat):
                next_echoarea = link[5:]
                go = False
            else:
                message_box("Конференция отсутствует в БД ноды")
        elif link[5:] in msgids:  # msgid in same echoarea
            if not stack or stack[-1] != msgn:
                stack.append(msgn)
            msgn = msgids.index(link[5:])
            prerender_msg_or_quit()
        else:
            msg, size = api.find_msg(link[5:])
            msgid = link[5:]
            body_tokens, body_height, scroll_thumb_size = prerender(msg[8:])
            if not stack or stack[-1] != msgn:
                stack.append(msgn)

    if msgids:
        read_msg_skip_twit(-1)
        if msgn < 0:
            next_echoarea = True
    body_tokens, body_height, scroll_thumb_size = prerender(msg[8:])

    while go:
        if msgids:
            draw_reader(msg[1], msgids[msgn], out)
            draw_status(len(version) + 2, utils.msgn_status(msgids, msgn, WIDTH))
            if echo.desc and WIDTH >= 80:
                draw_title(0, WIDTH - 2 - len(echo.desc), echo.desc)
            color = get_color("text")
            if not out:
                if WIDTH >= 80:
                    stdscr.addstr(1, 7, msg[3] + " (" + msg[4] + ")", color)
                else:
                    stdscr.addstr(1, 7, msg[3], color)
                msgtime = utils.msg_strftime(msg[2], WIDTH)
                stdscr.addstr(1, WIDTH - len(msgtime) - 1, msgtime, color)
            else:
                if cur_node.to:
                    stdscr.addstr(1, 7, cur_node.to[0], color)
            stdscr.addstr(2, 7, msg[5], color)
            stdscr.addstr(3, 7, msg[6][:WIDTH - 8], color)
            s_size = utils.msg_strfsize(size)
            draw_title(4, 0, s_size)
            tags = msg[0].split("/")
            if "repto" in tags and 36 + len(s_size) < WIDTH:
                repto = tags[tags.index("repto") + 1].strip()
                draw_title(4, len(s_size) + 3, "Ответ на " + repto)
            else:
                repto = False
            render_body(stdscr, body_tokens, y)
            if body_height > scroll_view:
                draw_scrollbar(stdscr, body_height,
                               scroll_thumb_size, scroll_view, y)
        else:
            draw_reader(echo.name, "", out)
        stdscr.attrset(get_color("border"))
        stdscr.refresh()
        key = stdscr.getch()
        if key == curses.KEY_RESIZE:
            y = 0
            get_term_size()
            scroll_view = HEIGHT - 5 - 1
            if msgids:
                body_tokens, body_height, scroll_thumb_size = prerender(msg[8:])
            stdscr.clear()
        elif key in keys.r_prev and msgn > 0 and msgids:
            y = 0
            msgn = msgn - 1
            stack.clear()
            tmp = msgn
            read_msg_skip_twit(-1)
            if msgn < 0:
                msgn = tmp + 1
            body_tokens, body_height, scroll_thumb_size = prerender(msg[8:])
        elif key in keys.r_next and msgn < len(msgids) - 1 and msgids:
            y = 0
            msgn = msgn + 1
            stack.clear()
            read_msg_skip_twit(+1)
            if msgn >= len(msgids):
                go = False
                next_echoarea = True
            body_tokens, body_height, scroll_thumb_size = prerender(msg[8:])
        elif key in keys.r_next and (msgn == len(msgids) - 1 or len(msgids) == 0):
            go = False
            next_echoarea = True
        elif key in keys.r_prep and not any((favorites, carbonarea, out)) and repto:
            if repto in msgids:
                y = 0
                stack.append(msgn)
                msgn = msgids.index(repto)
                msg, size = read_cur_msg()
                body_tokens, body_height, scroll_thumb_size = prerender(msg[8:])
        elif key in keys.r_nrep and len(stack) > 0:
            y = 0
            msgn = stack.pop()
            msg, size = read_cur_msg()
            body_tokens, body_height, scroll_thumb_size = prerender(msg[8:])
        elif key in keys.r_up and msgids:
            y = max(0, y - 1)
        elif key in keys.r_ppage and msgids:
            y = max(0, y - scroll_view)
        elif key in keys.r_npage and msgids:
            y = min(body_height - scroll_view, y + scroll_view)
        elif key in keys.r_home and msgids:
            y = 0
        elif key in keys.r_mend and msgids:
            y = max(0, body_height - scroll_view)
        elif key in keys.r_ukeys:
            if len(msgids) == 0 or y >= body_height - HEIGHT + 5:
                y = 0
                if msgn == len(msgids) - 1 or len(msgids) == 0:
                    next_echoarea = True
                    go = False
                else:
                    msgn = msgn + 1
                    stack.clear()
                    msg, size = read_cur_msg()
                    body_tokens, body_height, scroll_thumb_size = prerender(msg[8:])
            else:
                if msgids and body_height > scroll_view:
                    y = min(body_height - scroll_view, y + scroll_view)
        elif key in keys.r_down and msgids:
            y = min(body_height - scroll_view, y + 1)
        elif key in keys.r_begin and msgids:
            y = 0
            msgn = 0
            stack.clear()
            msg, size = read_cur_msg()
            body_tokens, body_height, scroll_thumb_size = prerender(msg[8:])
        elif key in keys.r_end and msgids:
            y = 0
            msgn = len(msgids) - 1
            stack.clear()
            msg, size = read_cur_msg()
            body_tokens, body_height, scroll_thumb_size = prerender(msg[8:])
        elif key in keys.r_ins and not any((archive, out, favorites, carbonarea)):
            with open("template.txt", "r") as t:
                with open("temp", "w") as f:
                    f.write(echo.name + "\n")
                    f.write("All\n")
                    f.write("No subject\n\n")
                    f.write(t.read())
            call_editor()
            stdscr.clear()
        elif key in keys.r_save and not out:
            save_message_to_file(msgids[msgn], echo.name)
        elif key in keys.r_favorites and not out:
            saved = api.save_to_favorites(msgids[msgn], msg)
            draw_message_box("Подождите", False)
            get_counts(False)
            if saved:
                message_box("Сообщение добавлено в избранные")
            else:
                message_box("Сообщение уже есть в избранных")
        elif key in keys.r_quote and not any((archive, out)) and msgids:
            quote_msg(msgids[msgn], msg)
            call_editor()
        elif key in keys.r_subj:
            show_subject(msg[6])
        elif key in keys.r_info and not out and WIDTH < 80:
            message_box("id  : " + msgids[msgn] + "\naddr: " + msg[4])
        elif key in keys.o_edit and out:
            if msgids[msgn].endswith(".out") or msgids[msgn].endswith(".draft"):
                copyfile("out/" + cur_node.nodename + "/" + msgids[msgn], "temp")
                call_editor(msgids[msgn])
                msgids = get_out_msgids(drafts)
                prerender_msg_or_quit()
            else:
                message_box("Сообщение уже отправлено")
            stdscr.clear()
        elif key in keys.f_delete and favorites and msgids:
            draw_message_box("Подождите", False)
            api.remove_from_favorites(msgids[msgn])
            get_counts(False)
            msgids = api.get_echo_msgids(echo.name)
            prerender_msg_or_quit()
        elif key in keys.r_getmsg and size == 0 and msgid:
            try:
                draw_message_box("Подождите", False)
                get_msg(msgid)
                get_counts(True)
                stdscr.clear()
                msg, size = api.find_msg(msgid)
                body_tokens, body_height, scroll_thumb_size = prerender(msg[8:])
            except Exception as ex:
                message_box("Не удалось определить msgid.\n" + str(ex))
                stdscr.clear()
        elif key in keys.r_links:
            results = parser.url_template.findall("\n".join(msg[8:]))
            links = [it[0] for it in results]
            links = list(map(
                lambda it: it[0:-1] if it.endswith(")") and "(" not in it else it,
                links))
            if len(links) == 1:
                open_link(links[0])
            elif links:
                i = show_menu("Выберите ссылку", links)
                if i:
                    open_link(links[i - 1])
            stdscr.clear()
        elif key in keys.r_to_out and drafts:
            node_dir = "out/" + cur_node.nodename
            os.rename(node_dir + "/" + msgids[msgn],
                      node_dir + "/" + msgids[msgn].replace(".draft", ".out"))
            msgids = get_out_msgids(drafts)
            prerender_msg_or_quit()
        elif key in keys.r_to_drafts and out and not drafts and msgids[msgn].endswith(".out"):
            node_dir = "out/" + cur_node.nodename
            os.rename(node_dir + "/" + msgids[msgn],
                      node_dir + "/" + msgids[msgn].replace(".out", ".draft"))
            msgids = get_out_msgids(drafts)
            prerender_msg_or_quit()
        elif key in keys.r_list and not out and not drafts:
            selected_msgn = show_msg_list_screen(echo, msgn)
            if selected_msgn > -1:
                y = 0
                msgn = selected_msgn
                stack.clear()
                msg, size = read_cur_msg()
                body_tokens, body_height, scroll_thumb_size = prerender(msg[8:])
        elif key in keys.r_quit:
            go = False
            next_echoarea = False
        elif key in keys.g_quit:
            go = False
            done = True
    lasts[echo.name] = msgn
    with open("lasts.lst", "wb") as f:
        pickle.dump(lasts, f)
    stdscr.clear()
    return done


def draw_msg_list(echo):
    stdscr.clear()
    color = get_color("border")
    stdscr.insstr(0, 0, "─" * WIDTH, color)
    if WIDTH >= 80:
        draw_title(0, 0, "Список сообщений в конференции " + echo)
    else:
        draw_title(0, 0, echo)


def show_msg_list_screen(echo: config.Echo, msgn):
    data = api.get_msg_list_data(echo.name)
    draw_msg_list(echo.name)
    echo_len = len(data)
    if echo_len <= HEIGHT - 1:
        start = 0
    elif msgn + HEIGHT - 1 < echo_len:
        start = msgn
    else:
        start = echo_len - HEIGHT + 1
    y = msgn - start
    while True:
        for i in range(1, HEIGHT):
            color = get_color("cursor" if i - 1 == y else "text")
            draw_cursor(i - 1, color)
            if start + i - 1 < echo_len:
                msg = data[start + i - 1]
                stdscr.addstr(i, 0, msg[1], color)
                stdscr.addstr(i, 16, msg[2][:WIDTH - 26], color)
                stdscr.insstr(i, WIDTH - 10, msg[3], color)
        key = stdscr.getch()
        if key in keys.s_up:
            y = y - 1
            if y == -1:
                y = 0
                start = max(0, start - 1)
        elif key in keys.s_down:
            y = y + 1
            if y > HEIGHT - 2:
                y = HEIGHT - 2
                if y + start + 1 < echo_len:
                    start += 1
            y = min(y, echo_len - 1)
        elif key in keys.s_ppage:
            if y == 0:
                start = max(0, start - HEIGHT + 1)
            y = 0
        elif key in keys.s_npage:
            if y == HEIGHT - 2:
                start = min(start + HEIGHT - 1, echo_len - HEIGHT + 1)
            y = min(echo_len - 1, HEIGHT - 2)
        elif key in keys.s_home:
            y = 0
            start = 0
        elif key in keys.s_end:
            y = min(echo_len - 1, HEIGHT - 2)
            start = max(0, echo_len - HEIGHT + 1)
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

config.ensure_exists()
reset_config()
cfg.load()
if cfg.db == "txt":
    import api.txt as api
elif cfg.db == "aio":
    import api.aio as api
elif cfg.db == "ait":
    import api.ait as api
elif cfg.db == "sqlite":
    import api.sqlite as api
else:
    raise Exception("Unsupported DB API :: " + cfg.db)
check_directories(api)
if cfg.keys == "default":
    import keys.default as keys
elif cfg.keys == "android":
    import keys.android as keys
elif cfg.keys == "vi":
    import keys.vi as keys
else:
    raise Exception("Unknown Keys Scheme :: " + cfg.keys)


def initialize_curses():
    curses.start_color()
    curses.use_default_colors()
    curses.noecho()
    curses.set_escdelay(50)  # ms
    curses.curs_set(0)
    curses.cbreak()
    stdscr.keypad(True)
    get_term_size()


def terminate_curses():
    curses.curs_set(1)
    stdscr.keypad(False)
    curses.echo(True)
    curses.nocbreak()
    curses.endwin()


stdscr = curses.initscr()
try:
    initialize_curses()
    try:
        config.load_colors(cfg.theme)
    except ValueError as err:
        config.load_colors("default")
        stdscr.refresh()
        message_box("Цветовая схема " + cfg.theme + " не установлена.\n"
                    + str(err) + "\nБудет использована схема по-умолчанию.")
        cfg.theme = "default"
    stdscr.bkgd(" ", get_color("text"))

    if cfg.splash:
        splash_screen()
    draw_message_box("Подождите", False)
    get_counts()
    stdscr.clear()
    show_echo_selector_screen()
finally:
    terminate_curses()
