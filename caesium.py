#!/usr/bin/env python3
# coding=utf-8
import base64
import codecs
import curses
import hashlib
import itertools
import locale
import os
import pickle
import re
import subprocess
import sys
import textwrap
import traceback
from shutil import copyfile
from typing import List, Optional

from core import (
    __version__, parser, client, config, ui, utils, search, outgoing,
    FEAT_X_C, FEAT_U_E,
)
from core.config import (
    get_color, UI_BORDER, UI_TEXT, UI_CURSOR, UI_STATUS, UI_TITLES
)

# TODO: Add http/https/socks proxy support
# import socket
# import socks
# socks.set_default_proxy(socks.SOCKS5, '127.0.0.1', 8081)
# socket.socket = socks.socksocket

blacklist = []
if os.path.exists("blacklist.txt"):
    with open("blacklist.txt", "r") as bl:
        blacklist = list(filter(None, map(lambda it: it.strip(),
                                          bl.readlines())))
node = 0
cfg = config.Config()

splash = ["▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀",
          "████████ ████████ ████████ ████████ ███ ███  ███ ██████████",
          "███           ███ ███  ███ ███          ███  ███ ███ ██ ███",
          "███      ████████ ████████ ████████ ███ ███  ███ ███ ██ ███",
          "███      ███  ███ ███           ███ ███ ███  ███ ███ ██ ███",
          "████████ ████████ ████████ ████████ ███ ████████ ███ ██ ███",
          "▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄",
          "           ncurses ii/idec client        v" + __version__,
          "           Andrew Lobanov             20.01.2026",
          "           Cthulhu Fhtagn"]


#
# Взаимодействие с нодой
#
def make_toss(node_):  # type: (config.Node) -> None
    node_dir = outgoing.directory(node_)
    lst = [x for x in os.listdir(node_dir)
           if x.endswith(".out")]
    for msg in lst:
        with codecs.open(node_dir + "%s" % msg, "r", "utf-8") as f:
            text_raw = f.read()
        text_b64 = base64.b64encode(text_raw.encode("utf-8")).decode("utf-8")
        with codecs.open(node_dir + "%s.toss" % msg, "w", "utf-8") as f:
            f.write(text_b64)
        os.rename(node_dir + "%s" % msg,
                  node_dir + "%s%s" % (msg, "msg"))


def send_mail(node_):  # type: (config.Node) -> None
    node_dir = outgoing.directory(node_)
    lst = [x for x in sorted(os.listdir(node_dir))
           if x.endswith(".toss")]
    total = str(len(lst))
    try:
        for n, msg in enumerate(lst, start=1):
            print("\rОтправка сообщения: " + str(n) + "/" + total, end="")
            msg_toss = node_dir + msg
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
    features = api.get_node_features(node_.nodename)
    if features is None:
        print("Запрос x/features...")
        features = client.get_features(node_.url)
        api.save_node_features(node_.nodename, features)
        print("  x/features: " + ", ".join(features))
    is_node_smart = FEAT_X_C in features and FEAT_U_E in features
    #
    echoareas = list(map(lambda e: e.name, filter(lambda e: e.sync,
                                                  node_.echoareas)))
    old_nec = None
    new_nec = None
    offsets = None
    if is_node_smart:
        old_nec = api.get_node_echo_counts(node_.nodename)
        new_nec = client.get_echo_count(node_.url, echoareas)
        offsets = utils.offsets_echo_count(old_nec or {}, new_nec)

    fetch_msg_list = []
    print("Получение индекса от ноды...")
    if is_node_smart and old_nec:
        remote_msg_list = []
        grouped = {offset: [ec[0] for ec in ec]
                   for offset, ec in itertools.groupby(offsets.items(),
                                                       lambda ec: ec[1])}
        for offset, echoareas in grouped.items():
            print("  offset %s: %s" % (str(offset), ", ".join(echoareas)))
            remote_msg_list += client.get_msg_list(node_.url, echoareas, offset)
    else:
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
    if is_node_smart:
        api.save_node_echo_counts(node_.nodename, new_nec)
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
        print(traceback.format_exc())
    input("Нажмите Enter для продолжения.")


#
# Пользовательский интерфейс
#
class Counts:
    total: dict[str, int]
    lasts: dict[str, int]
    counts: List[List[str]]

    def __init__(self):
        self.total = {}
        self.lasts = {}
        if os.path.exists("lasts.lst"):
            with open("lasts.lst", "rb") as f:
                self.lasts = pickle.load(f)

    def get_counts(self, node_, new=False):
        for echo in node_.echoareas:  # type: config.Echo
            if new or echo.name not in self.total:
                self.total[echo.name] = api.get_echo_length(echo.name)
        for echo in node_.archive:  # type: config.Echo
            if echo.name not in self.total:
                self.total[echo.name] = api.get_echo_length(echo.name)
        self.total[config.ECHO_CARBON.name] = len(api.get_carbonarea())
        self.total[config.ECHO_FAVORITES.name] = len(api.get_favorites_list())

    def rescan_counts(self, echoareas):
        self.counts = []
        for echo in echoareas:
            total = self.total[echo.name]
            if echo.name in self.lasts:
                unread = total - self.lasts[echo.name]
            else:
                unread = total + 1
            unread = max(1, unread)
            self.counts.append([str(total), str(unread - 1)])
        return self.counts

    def find_new(self, cursor):
        for n, (_, unread) in enumerate(self.counts):
            if n >= cursor and int(unread) > 0:
                return n
        return cursor


def edit_config():
    ui.terminate_curses()
    p = subprocess.Popen(cfg.editor + " " + config.CONFIG_FILEPATH, shell=True)
    p.wait()
    global node
    node = 0
    cfg.load()
    ui.initialize_curses()


class EchoSelectorScreen:
    echo_cursor: int = 0
    archive_cursor: int = 0
    next_echo: bool = False
    archive: bool = False
    cursor: int = 0
    echoareas: List[config.Echo] = None
    scroll: ui.ScrollCalc = None
    qs: Optional[search.QuickSearch] = None
    go: bool = True

    def __init__(self):
        self.counts = Counts()
        self.reload_echoareas()

    def reload_echoareas(self):
        self.archive = False
        self.echoareas = cfg.nodes[node].echoareas
        ui.draw_message_box("Подождите", False)
        self.counts.get_counts(cfg.nodes[node], False)
        self.counts.rescan_counts(self.echoareas)
        ui.stdscr.clear()
        self.cursor = 0
        self.scroll = ui.ScrollCalc(len(self.echoareas), ui.HEIGHT - 2)
        self.scroll.ensure_visible(self.cursor, center=True)

    def toggle_archive(self):
        self.archive = not self.archive
        if self.archive:
            self.echo_cursor = self.cursor
            self.cursor = self.archive_cursor
            self.echoareas = cfg.nodes[node].archive
        else:
            self.archive_cursor = self.cursor
            self.cursor = self.echo_cursor
            self.echoareas = cfg.nodes[node].echoareas
        ui.stdscr.clear()
        self.scroll = ui.ScrollCalc(len(self.echoareas), ui.HEIGHT - 2)
        self.scroll.ensure_visible(self.cursor, center=True)
        self.counts.rescan_counts(self.echoareas)

    # noinspection PyUnusedLocal
    @staticmethod
    def on_search_item(sidx, pattern, echo):
        result = []
        p = 0
        while match := pattern.search(echo.name, p):
            if p >= len(echo.name):
                break
            result.append(match)
            p = match.end()
        return [result] if result else None

    def show(self):
        while self.go:
            self.scroll.ensure_visible(self.cursor)
            self.draw(ui.stdscr, self.cursor, self.scroll, self.qs)
            #
            ks, key, _ = ui.get_keystroke()
            #
            if key == curses.KEY_RESIZE:
                ui.set_term_size()
                self.scroll = ui.ScrollCalc(len(self.echoareas), ui.HEIGHT - 2, self.cursor)
                ui.stdscr.clear()
                if self.qs:
                    self.qs.width = ui.WIDTH - len(ui.version) - 12
            elif self.qs:
                if key in keys.s_csearch:
                    self.qs = None
                    curses.curs_set(0)
                else:
                    self.qs.on_key_pressed_search(key, ks, self.scroll)
                    self.cursor = self.qs.ensure_cursor_visible(
                        key, self.cursor, self.scroll)
            elif key in keys.s_osearch:
                ui.stdscr.move(ui.HEIGHT - 1, len(ui.version) + 2)
                curses.curs_set(1)
                self.qs = search.QuickSearch(self.echoareas, self.on_search_item,
                                             ui.WIDTH - len(ui.version) - 12)
            elif key in keys.g_quit:
                self.go = False
            else:
                self.on_key_pressed(key)

    def draw(self, win, cursor, scroll, qs):
        h, w = win.getmaxyx()
        self.draw_echo_selector(win, scroll.pos, cursor, self.archive, qs,
                                self.counts.counts)
        if scroll.is_scrollable:
            ui.draw_scrollbarV(win, 1, w - 1, scroll)
        if qs:
            qs.draw(win, h - 1, len(ui.version) + 2, get_color(UI_STATUS))
            win.move(h - 1, len(ui.version) + 2 + self.qs.cursor)
        win.refresh()

    @staticmethod
    def draw_echo_selector(win, start, cursor, archive, qs, counts):
        # type: (curses.window, int, int, bool, search.QuickSearch, List[List[str]]) -> None
        h, w = win.getmaxyx()
        color = get_color(UI_BORDER)
        win.addstr(0, 0, "─" * w, color)
        cur_node = cfg.nodes[node]
        if archive:
            echoareas = cur_node.archive
            ui.draw_title(win, 0, 0, "Архив")
        else:
            echoareas = cur_node.echoareas
            ui.draw_title(win, 0, 0, "Конференция")
        #
        m = min(w - 38, max(map(lambda e: len(e.desc), echoareas)))
        count = "Сообщений"
        unread = "Не прочитано"
        description = "Описание"
        show_desc = (w >= 80) and m > 0
        if w < 80 or m == 0:
            m = len(unread) - 7
        ui.draw_title(win, 0, w + 2 - m - len(count) - len(unread) - 1, count)
        ui.draw_title(win, 0, w - 8 - m - 1, unread)
        if show_desc:
            ui.draw_title(win, 0, w - len(description) - 2, description)

        for y in range(1, h - 1):
            echoN = y - 1 + start
            if echoN == cursor:
                color = get_color(UI_CURSOR)
            else:
                color = get_color(UI_TEXT)
            win.addstr(y, 0, " " * w, color)
            if echoN >= len(echoareas):
                continue  #
            #
            win.attrset(color)
            echo = echoareas[echoN]
            total, unread = counts[echoN]
            if int(unread) > 0:
                win.addstr(y, 0, "+")
            win.addstr(y, 2, echo.name)
            win.addstr(y, w - 10 - m - len(total), total)
            win.addstr(y, w - 2 - m - len(unread), unread)
            if show_desc:
                win.addstr(y, max(w - m - 1, w - 1 - len(echo.desc)),
                           echo.desc[0:w - 38])
            #
            if qs and echoN in qs.result:
                idx = qs.result.index(echoN)
                for match in qs.matches[idx]:
                    win.addstr(y, 2 + match.start(),
                               echo.name[match.start():match.end()],
                               color | curses.A_REVERSE)

        ui.draw_status_bar(win, text=cur_node.nodename)

    def on_key_pressed(self, key):
        global node
        if key in keys.s_up:
            self.cursor = max(0, self.cursor - 1)
        elif key in keys.s_down:
            self.cursor = min(self.scroll.content - 1, self.cursor + 1)
        elif key in keys.s_ppage:
            if self.cursor > self.scroll.pos:
                self.cursor = self.scroll.pos
            else:
                self.cursor = max(0, self.cursor - self.scroll.view)
        elif key in keys.s_npage:
            page_bottom = self.scroll.pos_bottom()
            if self.cursor < page_bottom:
                self.cursor = page_bottom
            else:
                self.cursor = min(self.scroll.content - 1, page_bottom + self.scroll.view)
        elif key in keys.s_home:
            self.cursor = 0
        elif key in keys.s_end:
            self.cursor = self.scroll.content - 1
        elif key in keys.s_get:
            ui.terminate_curses()
            os.system('cls' if os.name == 'nt' else 'clear')
            fetch_mail(cfg.nodes[node])
            ui.initialize_curses()
            ui.draw_message_box("Подождите", False)
            self.counts.get_counts(cfg.nodes[node], True)
            self.counts.rescan_counts(self.echoareas)
            ui.stdscr.clear()
            self.cursor = self.counts.find_new(0)
        elif key in keys.s_archive and len(cfg.nodes[node].archive) > 0:
            self.toggle_archive()
        elif key in keys.s_enter:
            ui.draw_message_box("Подождите", False)
            last = 0
            cur_echo = self.echoareas[self.cursor]
            if cur_echo.name in self.counts.lasts:
                last = self.counts.lasts[cur_echo.name]
            last = min(self.counts.total[cur_echo.name], last + 1)
            self.go, self.next_echo = echo_reader(
                cur_echo, last, self.archive, self.counts)
            self.counts.rescan_counts(self.echoareas)
            if self.next_echo and isinstance(self.next_echo, bool):
                self.cursor = self.counts.find_new(self.cursor)
                self.next_echo = False
            elif self.next_echo and isinstance(self.next_echo, str):
                cur_node = cfg.nodes[node]
                if ((not self.archive and self.next_echo in cur_node.archive)
                        or (self.archive and (self.next_echo in cur_node.echoareas
                                              or self.next_echo in cur_node.stat))):
                    self.toggle_archive()
                # noinspection PyTypeChecker
                self.cursor = (self.echoareas.index(self.next_echo)
                               if self.next_echo in self.echoareas else
                               0)
                self.next_echo = False

        elif key in keys.s_out:
            out_length = outgoing.get_out_length(cfg.nodes[node], drafts=False)
            if out_length > -1:
                self.go, self.next_echo = echo_reader(
                    config.ECHO_OUT, out_length, self.archive, self.counts)
        elif key in keys.s_drafts:
            out_length = outgoing.get_out_length(cfg.nodes[node], drafts=True)
            if out_length > -1:
                self.go, self.next_echo = echo_reader(
                    config.ECHO_DRAFTS, out_length, self.archive, self.counts)
        elif key in keys.s_nnode:
            node = node + 1
            if node == len(cfg.nodes):
                node = 0
            self.reload_echoareas()
        elif key in keys.s_pnode:
            node = node - 1
            if node == -1:
                node = len(cfg.nodes) - 1
            self.reload_echoareas()
        elif key in keys.s_config:
            edit_config()
            config.load_colors(cfg.theme)
            node = 0
            self.reload_echoareas()


def draw_reader(echo: str, msgid, out, status_text=None):
    color = get_color(UI_BORDER)
    ui.stdscr.addstr(0, 0, "─" * ui.WIDTH, color)
    ui.stdscr.addstr(4, 0, "─" * ui.WIDTH, color)
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
    for i in range(1, 4):
        ui.stdscr.addstr(i, 0, " " * ui.WIDTH, 1)
    color = get_color(UI_TITLES)
    ui.stdscr.addstr(1, 1, "От:   ", color)
    ui.stdscr.addstr(2, 1, "Кому: ", color)
    ui.stdscr.addstr(3, 1, "Тема: ", color)
    ui.draw_status_bar(ui.stdscr, text=status_text)


def call_editor(node_, out=''):
    ui.terminate_curses()
    h = hashlib.sha1(str.encode(open("temp", "r", ).read())).hexdigest()
    p = subprocess.Popen(cfg.editor + " ./temp", shell=True)
    p.wait()
    ui.initialize_curses()
    if h != hashlib.sha1(str.encode(open("temp", "r", ).read())).hexdigest():
        d = ui.SelectWindow("Куда сохранить?", ["Сохранить в исходящие",
                                                "Сохранить как черновик"]
                            ).show()
        if d == 2:  # "Сохранить как черновик"
            if not out:
                outgoing.save_out(node_, extension=".draft")
            else:
                outgoing.resave_out(node_, out.replace(".out", ".draft"))
                if out.endswith(".out"):
                    os.remove(outgoing.directory(node_) + out)
        elif d == 1:  # "Сохранить в исходящие"
            if not out:
                outgoing.save_out(node_, extension=".out")
            else:
                outgoing.resave_out(node_, out.replace(".draft", ".out"))
                if out.endswith(".draft"):
                    os.remove(outgoing.directory(node_) + out)
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


def quote_msg(msgid, msg):
    with open("template.txt", "r") as t:
        with open("temp", "w") as f:
            subj = msg[6]
            if not msg[6].startswith("Re:"):
                subj = "Re: " + subj
            f.write(msg[1] + "\n")
            f.write(msg[3] + "\n")
            f.write(subj + "\n\n")
            f.write("@repto:" + msgid + "\n")
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


def save_attachment(token):  # type: (parser.Token) -> None
    filepath = "downloads/" + token.filename
    with open(filepath, "wb") as attachment:
        attachment.write(token.filedata)
    ui.draw_message_box("Файл сохранён '%s'" % filepath, True)
    ui.stdscr.getch()
    if ui.SelectWindow("Открыть '%s'?" % token.filename,
                       ["Нет", "Да"]).show() == 2:
        utils.open_file(filepath)


def echo_reader(echo: config.Echo, msgn, archive, counts):
    ui.stdscr.clear()
    ui.stdscr.attrset(get_color(UI_BORDER))
    out = (echo in (config.ECHO_OUT, config.ECHO_DRAFTS))
    drafts = (echo == config.ECHO_DRAFTS)
    favorites = (echo == config.ECHO_FAVORITES)
    carbonarea = (echo == config.ECHO_CARBON)
    cur_node = cfg.nodes[node]  # type: config.Node

    def get_msgids():
        if out:
            return outgoing.get_out_msgids(cur_node, drafts)
        elif favorites:
            return api.get_favorites_list()
        elif carbonarea:
            return api.get_carbonarea()
        else:
            return api.get_echo_msgids(echo.name)

    msgids = get_msgids()
    msgn = min(msgn, len(msgids) - 1)
    msg = ["", "", "", "", "", "", "", "", "Сообщение отсутствует в базе"]
    size = 0
    go = True
    done = False
    repto = False
    stack = []
    msgid = None  # non-current-echo message id, navigated by ii-link
    qs = None  # type: Optional[search.QuickSearch]
    next_echo = False

    def read_cur_msg():  # type: () -> (List[str], int)
        nonlocal msgid
        msgid = None
        if out:
            return outgoing.read_out_msg(msgids[msgn], cur_node)
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

    def prerender(msgbody, pos=0):
        tokens = parser.tokenize(msgbody)
        view = ui.HEIGHT - 5 - 1  # screen ui.HEIGHT - header - status line
        body_height = parser.prerender(tokens, ui.WIDTH, view)
        t2l_ = parser.token_line_map(tokens)
        return tokens, ui.ScrollCalc(body_height, view, pos), t2l_

    def prerender_msg_or_quit():
        nonlocal msgn, msg, size, go, body_tokens, scroll, t2l
        if msgids:
            msgn = min(msgn, len(msgids) - 1)
            msg, size = read_cur_msg()
            body_tokens, scroll, t2l = prerender(msg[8:])
        else:
            go = False

    def open_link(token):  # type: (parser.Token) -> None
        link = token.url
        nonlocal msgid, msgn, msg, size, go, body_tokens, scroll, t2l, next_echo
        if token.filename:
            if token.filedata:
                save_attachment(token)
        elif link.startswith("#"):  # markdown anchor?
            pos = parser.find_pos_by_anchor(body_tokens, token)
            if pos != -1:
                scroll.pos = pos
        elif not link.startswith("ii://"):
            if not cfg.browser.open(link):
                ui.show_message_box("Не удалось запустить Интернет-браузер")
        elif parser.echo_template.match(link[5:]):  # echoarea
            if echo.name == link[5:]:
                ui.show_message_box("Конференция уже открыта")
            elif (link[5:] in cur_node.echoareas
                  or link[5:] in cur_node.archive
                  or link[5:] in cur_node.stat):
                next_echo = link[5:]
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
            body_tokens, scroll, t2l = prerender(msg[8:])
            if not stack or stack[-1] != msgn:
                stack.append(msgn)

    def on_search_item(sidx, p, token):
        # type: (int, re.Pattern, parser.Token) -> List
        matches = []
        for offset, line in enumerate(token.render):
            pos = 0
            while match := p.search(line, pos):
                if pos >= len(line):
                    break
                matches.append((offset, match))
                pos = match.end()
        if matches:
            token.search_idx = sidx
            token.search_matches = matches
        else:
            token.search_idx = None
            token.search_matches = None
        return matches

    if msgids:
        read_msg_skip_twit(-1)
        if msgn < 0:
            next_echo = True
    body_tokens, scroll, t2l = prerender(msg[8:])

    while go:
        if msgids:
            draw_reader(msg[1], msgid or msgids[msgn], out,
                        status_text=utils.msgn_status(msgids, msgn, ui.WIDTH))
            if echo.desc and ui.WIDTH >= 80:
                ui.draw_title(ui.stdscr, 0, ui.WIDTH - 2 - len(echo.desc), echo.desc)
            color = get_color(UI_TEXT)
            if not out:
                if ui.WIDTH >= 80:
                    ui.stdscr.addstr(1, 7, msg[3] + " (" + msg[4] + ")", color)
                else:
                    ui.stdscr.addstr(1, 7, msg[3], color)
                msgtime = utils.msg_strftime(msg[2], ui.WIDTH)
                ui.stdscr.addstr(1, ui.WIDTH - len(msgtime) - 1, msgtime, color)
            elif cur_node.to:
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
            ui.render_body(ui.stdscr, body_tokens, scroll.pos, qs)
            if scroll.is_scrollable:
                ui.draw_scrollbarV(ui.stdscr, 5, ui.WIDTH - 1, scroll)
        else:
            draw_reader(echo.name, "", out)
        if qs:
            qs.draw(ui.stdscr, ui.HEIGHT - 1, len(ui.version) + 2,
                    get_color(UI_STATUS))
            ui.stdscr.move(ui.HEIGHT - 1, len(ui.version) + 2 + qs.cursor)
        ks, key, _ = ui.get_keystroke()
        if key == curses.KEY_RESIZE:
            ui.set_term_size()
            body_tokens, scroll, t2l = prerender(msg[8:], scroll.pos)
            ui.stdscr.clear()
            if qs:
                qs.items = body_tokens
                qs.width = ui.WIDTH - len(ui.version) - 12
                tnum, _ = parser.find_visible_token(body_tokens, scroll.pos)
                qs.search(qs.query, tnum)
        elif qs:
            if key in keys.s_csearch:
                qs = None
                curses.curs_set(0)
            else:
                pager = search.Pager(
                    parser.find_visible_token(body_tokens, scroll.pos)[0],
                    lambda: parser.find_visible_token(body_tokens, scroll.pos + scroll.view)[0],
                    lambda: parser.find_visible_token(body_tokens, scroll.pos)[0] - 1)
                qs.on_key_pressed_search(key, ks, pager)
                if qs.result:
                    tidx = qs.result[qs.idx]
                    off, _ = qs.matches[qs.idx]
                    if key in keys.s_home or key in keys.s_end:
                        scroll.ensure_visible(t2l[tidx].start + off, center=True)
                    elif key in keys.s_npage:
                        scroll.ensure_visible(t2l[tidx].start + off + scroll.view - 1)
                    elif key in keys.s_ppage:
                        scroll.ensure_visible(t2l[tidx].start + off - scroll.view + 1)
                    else:
                        scroll.ensure_visible(t2l[tidx].start + off)
        elif key in keys.r_prev and msgn > 0 and msgids:
            msgn = msgn - 1
            stack.clear()
            tmp = msgn
            read_msg_skip_twit(-1)
            if msgn < 0:
                msgn = tmp + 1
            body_tokens, scroll, t2l = prerender(msg[8:])
        elif key in keys.r_next and msgn < len(msgids) - 1 and msgids:
            msgn = msgn + 1
            stack.clear()
            read_msg_skip_twit(+1)
            if msgn >= len(msgids):
                go = False
                next_echo = True
            body_tokens, scroll, t2l = prerender(msg[8:])
        elif key in keys.r_next and (msgn == len(msgids) - 1 or len(msgids) == 0):
            go = False
            next_echo = True
        elif key in keys.r_prep and not any((favorites, carbonarea, out)) and repto:
            if repto in msgids:
                stack.append(msgn)
                msgn = msgids.index(repto)
                msg, size = read_cur_msg()
                body_tokens, scroll, t2l = prerender(msg[8:])
        elif key in keys.r_nrep and len(stack) > 0:
            msgn = stack.pop()
            msg, size = read_cur_msg()
            body_tokens, scroll, t2l = prerender(msg[8:])
        elif key in keys.r_up and msgids:
            scroll.pos -= 1
        elif key in keys.r_ppage and msgids:
            scroll.pos -= scroll.view
        elif key in keys.r_npage and msgids:
            scroll.pos += scroll.view
        elif key in keys.r_home and msgids:
            scroll.pos = 0
        elif key in keys.r_mend and msgids:
            scroll.pos = scroll.content - scroll.view
        elif key in keys.r_ukeys:
            if not msgids or scroll.pos >= scroll.content - scroll.view:
                if msgn == len(msgids) - 1 or not msgids:
                    next_echo = True
                    go = False
                else:
                    msgn = msgn + 1
                    stack.clear()
                    msg, size = read_cur_msg()
                    body_tokens, scroll, t2l = prerender(msg[8:])
            else:
                scroll.pos += scroll.view
        elif key in keys.r_down and msgids:
            scroll.pos += 1
        elif key in keys.r_begin and msgids:
            msgn = 0
            stack.clear()
            msg, size = read_cur_msg()
            body_tokens, scroll, t2l = prerender(msg[8:])
        elif key in keys.r_end and msgids:
            msgn = len(msgids) - 1
            stack.clear()
            msg, size = read_cur_msg()
            body_tokens, scroll, t2l = prerender(msg[8:])
        elif key in keys.r_ins and not any((archive, out, favorites, carbonarea)):
            with open("template.txt", "r") as t:
                with open("temp", "w") as f:
                    f.write(echo.name + "\n")
                    f.write("All\n")
                    f.write("No subject\n\n")
                    f.write(t.read())
            call_editor(cur_node)
        elif key in keys.r_save and not out:
            save_message_to_file(msgid or msgids[msgn], msg[1])
        elif key in keys.r_favorites and not out:
            saved = api.save_to_favorites(msgid or msgids[msgn], msg)
            ui.draw_message_box("Подождите", False)
            counts.get_counts(cur_node, False)
            ui.show_message_box("Сообщение добавлено в избранные" if saved else
                                "Сообщение уже есть в избранных")
        elif key in keys.r_quote and not any((archive, out)) and msgids:
            quote_msg(msgid or msgids[msgn], msg)
            call_editor(cur_node)
        elif key in keys.r_info:
            subj = textwrap.fill(msg[6], ui.WIDTH * 0.75,
                                 subsequent_indent="      ")
            ui.show_message_box("id:   %s\naddr: %s\nsubj: %s"
                                % (msgid or msgids[msgn], msg[4], subj))
        elif key in keys.o_edit and out:
            if msgids[msgn].endswith(".out") or msgids[msgn].endswith(".draft"):
                copyfile(outgoing.directory(cur_node) + msgids[msgn], "temp")
                call_editor(cur_node, msgids[msgn])
                msgids = get_msgids()
                prerender_msg_or_quit()
            else:
                ui.show_message_box("Сообщение уже отправлено")
            ui.stdscr.clear()
        elif key in keys.f_delete and favorites and msgids:
            ui.draw_message_box("Подождите", False)
            api.remove_from_favorites(msgids[msgn])
            counts.get_counts(cur_node, False)
            msgids = get_msgids()
            prerender_msg_or_quit()
        elif key in keys.f_delete and drafts and msgids:
            if ui.SelectWindow("Удалить черновик '%s'?" % msgids[msgn],
                               ["Нет", "Да"]).show() == 2:
                os.remove(outgoing.directory(cur_node) + msgids[msgn])
                msgids = get_msgids()
                prerender_msg_or_quit()
        elif key in keys.r_getmsg and size == 0 and msgid:
            try:
                ui.draw_message_box("Подождите", False)
                get_msg(msgid)
                counts.get_counts(cur_node, True)
                ui.stdscr.clear()
                msg, size = api.find_msg(msgid)
                body_tokens, scroll, t2l = prerender(msg[8:])
            except Exception as ex:
                ui.show_message_box("Не удалось определить msgid.\n" + str(ex))
                ui.stdscr.clear()
        elif key in keys.r_links:
            links = list(filter(lambda it: it.type == parser.TT.URL,
                                body_tokens))
            if len(links) == 1:
                open_link(links[0])
            elif links:
                win = ui.SelectWindow("Выберите ссылку", list(map(
                    lambda it: (it.url + " " + (it.title or "")).strip(),
                    links)))
                i = win.show()
                if win.resized:
                    body_tokens, scroll, t2l = prerender(msg[8:], scroll.pos)
                if i:
                    open_link(links[i - 1])
            ui.stdscr.clear()
        elif key in keys.r_to_out and drafts:
            draft_msg = outgoing.directory(cur_node) + msgids[msgn]
            os.rename(draft_msg, draft_msg.replace(".draft", ".out"))
            msgids = get_msgids()
            prerender_msg_or_quit()
        elif key in keys.r_to_drafts and out and not drafts and msgids[msgn].endswith(".out"):
            out_msg = outgoing.directory(cur_node) + msgids[msgn]
            os.rename(out_msg, out_msg.replace(".out", ".draft"))
            msgids = get_msgids()
            prerender_msg_or_quit()
        elif key in keys.r_list and not out and not drafts:
            data = api.get_msg_list_data(echo.name)
            win = ui.MsgListScreen(echo.name, data, msgn)
            selected_msgn = win.show()
            if win.resized:
                body_tokens, scroll, t2l = prerender(msg[8:], scroll.pos)
            if selected_msgn > -1:
                msgn = selected_msgn
                stack.clear()
                msg, size = read_cur_msg()
                body_tokens, scroll, t2l = prerender(msg[8:])
        elif key in keys.r_inlines:
            parser.INLINE_STYLE_ENABLED = not parser.INLINE_STYLE_ENABLED
            body_tokens, scroll, t2l = prerender(msg[8:], scroll.pos)
        elif key in keys.s_osearch:
            ui.stdscr.move(ui.HEIGHT - 1, len(ui.version) + 2)
            curses.curs_set(1)
            qs = search.QuickSearch(body_tokens, on_search_item,
                                    ui.WIDTH - len(ui.version) - 12)
        elif key in keys.r_quit:
            go = False
            next_echo = False
        elif key in keys.g_quit:
            go = False
            done = True
    counts.lasts[echo.name] = msgn
    with open("lasts.lst", "wb") as f:
        pickle.dump(counts.lasts, f)
    ui.stdscr.clear()
    return not done, next_echo


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
# create directories
api.init()
if not os.path.exists("downloads"):
    os.mkdir("downloads")
outgoing.init(cfg)
#
if cfg.keys == "default":
    import keys.default as keys
elif cfg.keys == "android":
    import keys.android as keys
elif cfg.keys == "vi":
    import keys.vi as keys
else:
    raise Exception("Unknown Keys Scheme :: " + cfg.keys)
ui.keys = keys
search.keys = keys

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
    EchoSelectorScreen().show()
finally:
    ui.terminate_curses()
