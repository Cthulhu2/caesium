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

from core import parser, client, config, ui, utils
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

version = "Caesium/0.7 │"
client.USER_AGENT = "Caesium/0.7"

splash = ["▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀",
          "████████ ████████ ████████ ████████ ███ ███  ███ ██████████",
          "███           ███ ███  ███ ███          ███  ███ ███ ██ ███",
          "███      ████████ ████████ ████████ ███ ███  ███ ███ ██ ███",
          "███      ███  ███ ███           ███ ███ ███  ███ ███ ██ ███",
          "████████ ████████ ████████ ████████ ███ ████████ ███ ██ ███",
          "▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄",
          "           ncurses ii/idec client        v0.7",
          "           Andrew Lobanov             20.01.2026",
          "           Cthulhu Fhtagn"]


def check_directories(storage_api):
    if not os.path.exists("downloads"):
        os.mkdir("downloads")
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
    num = 0
    for x in os.listdir(outpath):
        s_num = x.split(".", maxsplit=1)[0]
        if s_num.isdigit():
            num = max(num, int(s_num))
    return outpath + "/%s" % str(num + 1).zfill(5)


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


def draw_cursor(y, color):
    ui.stdscr.insstr(y + 1, 0, " " * ui.WIDTH, color)


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
    ui.stdscr.attrset(get_color("border"))
    color = get_color("border")
    ui.stdscr.insstr(0, 0, "─" * ui.WIDTH, color)
    cur_node = cfg.nodes[node]
    if archive:
        echoareas = cur_node.archive
        ui.draw_title(ui.stdscr, 0, 0, "Архив")
    else:
        echoareas = cur_node.echoareas
        ui.draw_title(ui.stdscr, 0, 0, "Конференция")
    for echo in echoareas:
        desc_len = len(echo.desc)
        if desc_len > m:
            m = desc_len
        if m > ui.WIDTH - 38:
            m = ui.WIDTH - 38
        dsc_lens.append(desc_len)
    y = 0
    count = "Сообщений"
    unread = "Не прочитано"
    description = "Описание"
    if ui.WIDTH < 80 or m == 0:
        m = len(unread) - 7
        hidedsc = True
    ui.draw_title(ui.stdscr, 0, ui.WIDTH + 2 - m - len(count) - len(unread) - 1, count)
    ui.draw_title(ui.stdscr, 0, ui.WIDTH - 8 - m - 1, unread)
    if not hidedsc:
        ui.draw_title(ui.stdscr, 0, ui.WIDTH - len(description) - 2, description)
    for echo in echoareas:
        if y - start < ui.HEIGHT - 2:
            if y == cursor:
                if y >= start:
                    color = get_color("cursor")
                    ui.stdscr.attrset(color)
                    draw_cursor(y - start, color)
            else:
                if y >= start:
                    color = get_color("text")
                    draw_cursor(y - start, color)
                ui.stdscr.attrset(get_color("text"))
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
                    ui.stdscr.addstr(y + 1 - start, 0, "+")
                ui.stdscr.addstr(y + 1 - start, 2, echo.name)
                if ui.WIDTH >= 80:
                    if ui.WIDTH - 38 >= len(echo.desc):
                        ui.stdscr.addstr(y + 1 - start, ui.WIDTH - 1 - dsc_lens[y],
                                         echo.desc, color)
                    else:
                        cut_index = ui.WIDTH - 38 - len(echo.desc)
                        ui.stdscr.addstr(y + 1 - start, ui.WIDTH - 1 - len(echo.desc[:cut_index]),
                                         echo.desc[:cut_index])
                ui.stdscr.addstr(y + 1 - start, ui.WIDTH - 10 - m - len(counts[y][0]), counts[y][0])
                ui.stdscr.addstr(y + 1 - start, ui.WIDTH - 2 - m - len(counts[y][1]), counts[y][1])
        y = y + 1

    color = get_color("statusline")
    ui.stdscr.insstr(ui.HEIGHT - 1, 0, " " * ui.WIDTH, color)
    ui.stdscr.addstr(ui.HEIGHT - 1, 1, version, color)
    ui.stdscr.addstr(ui.HEIGHT - 1, len(version) + 2, cur_node.nodename, color)
    ui.stdscr.addstr(ui.HEIGHT - 1, ui.WIDTH - 8, "│ " + datetime.now().strftime("%H:%M"), color)
    ui.stdscr.refresh()


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
    ui.terminate_curses()
    p = subprocess.Popen(cfg.editor + " " + config.CONFIG_FILEPATH, shell=True)
    p.wait()
    global node
    node = 0
    cfg.load()
    ui.initialize_curses()


def show_echo_selector_screen():
    global echo_cursor, archive_cursor, counts, counts_rescan, next_echoarea, node
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
        ui.stdscr.clear()
        counts_rescan = True

    def ensure_cursor_visible():
        nonlocal start
        if cursor - start > ui.HEIGHT - 3:
            start = cursor - ui.HEIGHT + 3
        elif cursor - start < 0:
            start = cursor

    while go:
        draw_echo_selector(start, cursor, archive)
        key = ui.stdscr.getch()
        if key == curses.KEY_RESIZE:
            ui.set_term_size()
            if cursor >= ui.HEIGHT - 2:
                start = cursor - ui.HEIGHT + 3
            if cursor - start <= 0:
                start = cursor
            if start > 0 and ui.HEIGHT - 2 > len(echoareas):
                start = 0
            ui.stdscr.clear()
        elif key in keys.s_up and cursor > 0:
            cursor = cursor - 1
            if cursor - start < 0 < start:
                start = start - 1
        elif key in keys.s_down and cursor < len(echoareas) - 1:
            cursor = cursor + 1
            if cursor - start > ui.HEIGHT - 3 and start < len(echoareas) - ui.HEIGHT + 2:
                start = start + 1
        elif key in keys.s_ppage:
            cursor = cursor - ui.HEIGHT + 2
            if cursor < 0:
                cursor = 0
            if cursor - start < 0 < start:
                start = start - ui.HEIGHT + 2
            if start < 0:
                start = 0
        elif key in keys.s_npage:
            cursor = cursor + ui.HEIGHT - 2
            if cursor >= len(echoareas):
                cursor = len(echoareas) - 1
            if cursor - start > ui.HEIGHT - 3:
                start = start + ui.HEIGHT - 2
                if start > len(echoareas) - ui.HEIGHT + 2:
                    start = len(echoareas) - ui.HEIGHT + 2
        elif key in keys.s_home:
            cursor = 0
            start = 0
        elif key in keys.s_end:
            cursor = len(echoareas) - 1
            if len(echoareas) >= ui.HEIGHT - 2:
                start = len(echoareas) - ui.HEIGHT + 2
        elif key in keys.s_get:
            ui.terminate_curses()
            os.system('cls' if os.name == 'nt' else 'clear')
            fetch_mail(cfg.nodes[node])
            ui.initialize_curses()
            ui.draw_message_box("Подождите", False)
            get_counts(True)
            ui.stdscr.clear()
            counts = rescan_counts(echoareas)
            cursor = find_new(0)
            if cursor >= ui.HEIGHT - 2:
                start = cursor - ui.HEIGHT + 3
            if cursor - start <= 0:
                start = cursor
        elif key in keys.s_archive and len(cfg.nodes[node].archive) > 0:
            toggle_archive()
            ensure_cursor_visible()
        elif key in keys.s_enter:
            ui.draw_message_box("Подождите", False)
            if echoareas[cursor].name in lasts:
                last = lasts[echoareas[cursor].name]
            else:
                last = 0
            if echoareas[cursor] == config.ECHO_FAVORITES:
                echo_length = len(api.get_favorites_list())
            elif echoareas[cursor] == config.ECHO_CARBON:
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
            ui.draw_message_box("Подождите", False)
            get_counts()
            ui.stdscr.clear()
            counts_rescan = True
            cursor = 0
            start = 0
        elif key in keys.s_pnode:
            archive = False
            node = node - 1
            if node == -1:
                node = len(cfg.nodes) - 1
            echoareas = cfg.nodes[node].echoareas
            ui.draw_message_box("Подождите", False)
            get_counts()
            ui.stdscr.clear()
            counts_rescan = True
            cursor = 0
            start = 0
        elif key in keys.s_config:
            edit_config()
            config.load_colors(cfg.theme)
            get_counts()
            ui.stdscr.clear()
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


# region Render Body
def render_body(scr, tokens, scroll):
    tnum, offset = parser.find_visible_token(tokens, scroll)
    line_num = tokens[tnum].line_num
    for y in range(5, ui.HEIGHT - 1):
        scr.addstr(y, 0, " " * ui.WIDTH, 1)
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
        if y >= ui.HEIGHT - 1:
            break  # tokens
        #
        text_attr = apply_attribute(token, text_attr)
        #
        y, x = render_token(scr, token, y, x, offset, text_attr)
        offset = 0  # required in the first partial multiline token only


def apply_attribute(token, text_attr):
    if token.type == parser.TT.ITALIC_BEGIN:
        text_attr |= curses.A_ITALIC
    elif token.type == parser.TT.ITALIC_END:
        text_attr &= ~curses.A_ITALIC

    elif token.type == parser.TT.BOLD_BEGIN:
        text_attr |= curses.A_BOLD
    elif token.type == parser.TT.BOLD_END:
        text_attr &= ~curses.A_BOLD
    return text_attr


def render_token(scr, token: parser.Token, y, x, offset, text_attr):
    for i, line in enumerate(token.render[offset:]):
        if y + i >= ui.HEIGHT - 1:
            return y + i, x  #
        attr = get_color("text")
        if token.type in (parser.TT.CODE, parser.TT.COMMENT, parser.TT.HEADER,
                          parser.TT.ORIGIN, parser.TT.QUOTE1, parser.TT.QUOTE2,
                          parser.TT.URL):
            attr = get_color(token.type.name.lower())
        if line:
            scr.addstr(y + i, x, line, attr | text_attr)

        if len(token.render) > 1 and i + offset < len(token.render) - 1:
            x = 0  # new line in multiline token -- carriage return
        else:
            x += len(line)  # last/single line -- move caret in line
    return y + (len(token.render) - 1) - offset, x  #
# endregion Render Body


def draw_reader(echo: str, msgid, out):
    color = get_color("border")
    ui.stdscr.insstr(0, 0, "─" * ui.WIDTH, color)
    ui.stdscr.insstr(4, 0, "─" * ui.WIDTH, color)
    if out:
        ui.draw_title(ui.stdscr, 0, 0, echo)
        if msgid.endswith(".out"):
            ns = "не отправлено"
            ui.draw_title(ui.stdscr, 4, ui.WIDTH - len(ns) - 2, ns)
    else:
        if ui.WIDTH >= 80:
            ui.draw_title(ui.stdscr, 0, 0, echo + " / " + msgid)
        else:
            ui.draw_title(ui.stdscr, 0, 0, echo)
    for i in range(0, 3):
        draw_cursor(i, 1)
    color = get_color("titles")
    ui.stdscr.addstr(1, 1, "От:   ", color)
    ui.stdscr.addstr(2, 1, "Кому: ", color)
    ui.stdscr.addstr(3, 1, "Тема: ", color)
    #
    color = get_color("statusline")
    ui.stdscr.insstr(ui.HEIGHT - 1, 0, " " * ui.WIDTH, color)
    ui.stdscr.addstr(ui.HEIGHT - 1, 1, version, color)
    ui.stdscr.addstr(ui.HEIGHT - 1, ui.WIDTH - 8, "│ " + datetime.now().strftime("%H:%M"), color)
    if parser.INLINE_STYLE_ENABLED:
        ui.stdscr.addstr(ui.HEIGHT - 1, ui.WIDTH - 10, "~", color)


def draw_scrollbar(scr, body_height, thumb_size, scroll_view, y):
    scr.attrset(get_color("scrollbar"))
    for i in range(5, ui.HEIGHT - 1):
        scr.addstr(i, ui.WIDTH - 1, "░")
    thumb_y = utils.scroll_thumb_pos(body_height, y, scroll_view, thumb_size)
    for i in range(thumb_y + 5, thumb_y + 5 + thumb_size):
        if i < ui.HEIGHT - 1:
            scr.addstr(i, ui.WIDTH - 1, "█")


def call_editor(out=''):
    ui.terminate_curses()
    h = hashlib.sha1(str.encode(open("temp", "r", ).read())).hexdigest()
    p = subprocess.Popen(cfg.editor + " ./temp", shell=True)
    p.wait()
    ui.initialize_curses()
    if h != hashlib.sha1(str.encode(open("temp", "r", ).read())).hexdigest():
        d = ui.show_menu("Куда сохранить?", ["Сохранить в исходящие",
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


def save_message_to_file(msgid, echoarea):
    msg, size = api.read_msg(msgid, echoarea)
    filepath = "downloads/" + msgid + ".txt"
    with open(filepath, "w") as f:
        f.write("== " + msg[1] + " ==================== " + msgid + "\n")
        f.write("От:   " + msg[3] + " (" + msg[4] + ")\n")
        f.write("Кому: " + msg[5] + "\n")
        f.write("Тема: " + msg[6] + "\n")
        f.write("\n".join(msg[7:]))
    ui.show_message_box("Сообщение сохранено в файл\n" + filepath)


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
    if len(subject) > ui.WIDTH - 8:
        msg = ""
        line = ""
        for word in subject.split(" "):
            if len(line + word) <= ui.WIDTH - 4:
                line = line + word + " "
            else:
                msg = msg + line + "\n"
                line = word + " "
        msg = msg + line
        ui.show_message_box(msg)


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


def echo_reader(echo: config.Echo, msgn, archive):
    global next_echoarea
    ui.stdscr.clear()
    ui.stdscr.attrset(get_color("border"))
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
    scroll_view = ui.HEIGHT - 5 - 1  # screen ui.HEIGHT - header - status line
    msg = ["", "", "", "", "", "", "", "", "Сообщение отсутствует в базе"]
    size = 0
    go = True
    done = False
    repto = False
    stack = []
    msgid = None  # non-current-echo message id, navigated by ii-link

    def read_cur_msg():  # type: () -> (List[str], int)
        nonlocal msgid
        msgid = None
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
        b_height = parser.prerender(tokens, ui.WIDTH, scroll_view)
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

    def open_link(token):  # type: (parser.Token) -> None
        link = token.value
        nonlocal msgid, msgn, msg, size, go
        nonlocal body_tokens, body_height, scroll_thumb_size
        global next_echoarea
        if hasattr(token, "filename"):
            if hasattr(token, "filedata"):
                filepath = "downloads/" + token.filename
                with open(filepath, "wb") as attachment:
                    attachment.write(token.filedata)
                ui.draw_message_box("Файл сохранён '%s'" % filepath, True)
                ui.stdscr.getch()
                if ui.show_menu("Открыть '%s'?" % token.filename,
                                ["Нет", "Да"]) == 2:
                    utils.open_file(filepath)
        elif not link.startswith("ii://"):
            if not cfg.browser.open(link):
                ui.show_message_box("Не удалось запустить Интернет-браузер")
        elif parser.echo_template.match(link[5:]):  # echoarea
            if echo.name == link[5:]:
                ui.show_message_box("Конференция уже открыта")
            elif (link[5:] in cur_node.echoareas
                  or link[5:] in cur_node.archive
                  or link[5:] in cur_node.stat):
                next_echoarea = link[5:]
                go = False
            else:
                ui.show_message_box("Конференция отсутствует в БД ноды")
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
            draw_reader(msg[1], msgid or msgids[msgn], out)
            ui.stdscr.addstr(ui.HEIGHT - 1, len(version) + 2,
                             utils.msgn_status(msgids, msgn, ui.WIDTH),
                             get_color("statusline"))
            if echo.desc and ui.WIDTH >= 80:
                ui.draw_title(ui.stdscr, 0, ui.WIDTH - 2 - len(echo.desc), echo.desc)
            color = get_color("text")
            if not out:
                if ui.WIDTH >= 80:
                    ui.stdscr.addstr(1, 7, msg[3] + " (" + msg[4] + ")", color)
                else:
                    ui.stdscr.addstr(1, 7, msg[3], color)
                msgtime = utils.msg_strftime(msg[2], ui.WIDTH)
                ui.stdscr.addstr(1, ui.WIDTH - len(msgtime) - 1, msgtime, color)
            else:
                if cur_node.to:
                    ui.stdscr.addstr(1, 7, cur_node.to[0], color)
            ui.stdscr.addstr(2, 7, msg[5], color)
            ui.stdscr.addstr(3, 7, msg[6][:ui.WIDTH - 8], color)
            s_size = utils.msg_strfsize(size)
            ui.draw_title(ui.stdscr, 4, 0, s_size)
            tags = msg[0].split("/")
            if "repto" in tags and 36 + len(s_size) < ui.WIDTH:
                repto = tags[tags.index("repto") + 1].strip()
                ui.draw_title(ui.stdscr, 4, len(s_size) + 3, "Ответ на " + repto)
            else:
                repto = False
            render_body(ui.stdscr, body_tokens, y)
            if body_height > scroll_view:
                draw_scrollbar(ui.stdscr, body_height,
                               scroll_thumb_size, scroll_view, y)
        else:
            draw_reader(echo.name, "", out)
        ui.stdscr.attrset(get_color("border"))
        ui.stdscr.refresh()
        key = ui.stdscr.getch()
        if key == curses.KEY_RESIZE:
            y = 0
            ui.set_term_size()
            scroll_view = ui.HEIGHT - 5 - 1
            if msgids:
                body_tokens, body_height, scroll_thumb_size = prerender(msg[8:])
            ui.stdscr.clear()
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
            if len(msgids) == 0 or y >= body_height - ui.HEIGHT + 5:
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
            ui.stdscr.clear()
        elif key in keys.r_save and not out:
            save_message_to_file(msgid or msgids[msgn], msg[1])
        elif key in keys.r_favorites and not out:
            saved = api.save_to_favorites(msgids[msgn], msg)
            ui.draw_message_box("Подождите", False)
            get_counts(False)
            if saved:
                ui.show_message_box("Сообщение добавлено в избранные")
            else:
                ui.show_message_box("Сообщение уже есть в избранных")
        elif key in keys.r_quote and not any((archive, out)) and msgids:
            quote_msg(msgids[msgn], msg)
            call_editor()
        elif key in keys.r_subj:
            show_subject(msg[6])
        elif key in keys.r_info and not out and ui.WIDTH < 80:
            ui.show_message_box("id  : " + msgids[msgn] + "\naddr: " + msg[4])
        elif key in keys.o_edit and out:
            if msgids[msgn].endswith(".out") or msgids[msgn].endswith(".draft"):
                copyfile("out/" + cur_node.nodename + "/" + msgids[msgn], "temp")
                call_editor(msgids[msgn])
                msgids = get_out_msgids(drafts)
                prerender_msg_or_quit()
            else:
                ui.show_message_box("Сообщение уже отправлено")
            ui.stdscr.clear()
        elif key in keys.f_delete and favorites and msgids:
            ui.draw_message_box("Подождите", False)
            api.remove_from_favorites(msgids[msgn])
            get_counts(False)
            msgids = api.get_echo_msgids(echo.name)
            prerender_msg_or_quit()
        elif key in keys.f_delete and drafts and msgids:
            if ui.show_menu("Удалить черновик '%s'?" % msgids[msgn],
                            ["Нет", "Да"]) == 2:
                os.remove("out/" + cur_node.nodename + "/" + msgids[msgn])
                msgids = get_out_msgids(drafts)
                prerender_msg_or_quit()
        elif key in keys.r_getmsg and size == 0 and msgid:
            try:
                ui.draw_message_box("Подождите", False)
                get_msg(msgid)
                get_counts(True)
                ui.stdscr.clear()
                msg, size = api.find_msg(msgid)
                body_tokens, body_height, scroll_thumb_size = prerender(msg[8:])
            except Exception as ex:
                ui.show_message_box("Не удалось определить msgid.\n" + str(ex))
                ui.stdscr.clear()
        elif key in keys.r_links:
            links = list(filter(lambda it: it.type == parser.TT.URL,
                                body_tokens))
            if len(links) == 1:
                open_link(links[0])
            elif links:
                if i := ui.show_menu("Выберите ссылку",
                                     list(map(lambda it: it.value, links))):
                    open_link(links[i - 1])
            ui.stdscr.clear()
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
        elif key in keys.r_inlines:
            parser.INLINE_STYLE_ENABLED = not parser.INLINE_STYLE_ENABLED
            if msg:
                body_tokens, body_height, scroll_thumb_size = prerender(msg[8:])
                y = max(0, min(y, body_height - scroll_view))
        elif key in keys.r_quit:
            go = False
            next_echoarea = False
        elif key in keys.g_quit:
            go = False
            done = True
    lasts[echo.name] = msgn
    with open("lasts.lst", "wb") as f:
        pickle.dump(lasts, f)
    ui.stdscr.clear()
    return done


def draw_msg_list(echo):
    ui.stdscr.clear()
    color = get_color("border")
    ui.stdscr.insstr(0, 0, "─" * ui.WIDTH, color)
    if ui.WIDTH >= 80:
        ui.draw_title(ui.stdscr, 0, 0, "Список сообщений в конференции " + echo)
    else:
        ui.draw_title(ui.stdscr, 0, 0, echo)


def show_msg_list_screen(echo: config.Echo, msgn):
    data = api.get_msg_list_data(echo.name)
    draw_msg_list(echo.name)
    echo_len = len(data)
    if echo_len <= ui.HEIGHT - 1:
        start = 0
    elif msgn + ui.HEIGHT - 1 < echo_len:
        start = msgn
    else:
        start = echo_len - ui.HEIGHT + 1
    y = msgn - start
    while True:
        for i in range(1, ui.HEIGHT):
            color = get_color("cursor" if i - 1 == y else "text")
            draw_cursor(i - 1, color)
            if start + i - 1 < echo_len:
                msg = data[start + i - 1]
                ui.stdscr.addstr(i, 0, msg[1], color)
                ui.stdscr.addstr(i, 16, msg[2][:ui.WIDTH - 26], color)
                ui.stdscr.insstr(i, ui.WIDTH - 10, msg[3], color)
        key = ui.stdscr.getch()
        if key in keys.s_up:
            y = y - 1
            if y == -1:
                y = 0
                start = max(0, start - 1)
        elif key in keys.s_down:
            y = y + 1
            if y > ui.HEIGHT - 2:
                y = ui.HEIGHT - 2
                if y + start + 1 < echo_len:
                    start += 1
            y = min(y, echo_len - 1)
        elif key in keys.s_ppage:
            if y == 0:
                start = max(0, start - ui.HEIGHT + 1)
            y = 0
        elif key in keys.s_npage:
            if y == ui.HEIGHT - 2:
                start = min(start + ui.HEIGHT - 1, echo_len - ui.HEIGHT + 1)
            y = min(echo_len - 1, ui.HEIGHT - 2)
        elif key in keys.s_home:
            y = 0
            start = 0
        elif key in keys.s_end:
            y = min(echo_len - 1, ui.HEIGHT - 2)
            start = max(0, echo_len - ui.HEIGHT + 1)
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
ui.keys = keys

try:
    ui.initialize_curses()
    try:
        config.load_colors(cfg.theme)
    except ValueError as err:
        config.load_colors("default")
        ui.stdscr.refresh()
        ui.show_message_box("Цветовая схема %s не установлена.\n"
                            "%s\n"
                            "Будет использована схема по-умолчанию."
                            % (cfg.theme, str(err)))
        cfg.theme = "default"
    ui.stdscr.bkgd(" ", get_color("text"))

    if cfg.splash:
        ui.draw_splash(ui.stdscr, splash)
        curses.napms(2000)
        ui.stdscr.clear()
    ui.draw_message_box("Подождите", False)
    get_counts()
    ui.stdscr.clear()
    show_echo_selector_screen()
finally:
    ui.terminate_curses()
