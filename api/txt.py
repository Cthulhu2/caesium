# coding=utf-8
import codecs
import os
import time
from collections import defaultdict
from typing import Optional, List

storage = "txt"


def init(directory=""):
    global storage
    storage = directory
    if storage:
        if not storage.endswith("/"):
            storage += "/"
        if not os.path.exists(storage):
            os.mkdir(storage)
    if not os.path.exists(storage + "echo"):
        os.mkdir(storage + "echo")
    if not os.path.exists(storage + "msg"):
        os.mkdir(storage + "msg")
    if not os.path.exists(storage + "echo/favorites"):
        open(storage + "echo/favorites", "w")
    if not os.path.exists("echo/carbonarea"):
        open(storage + "echo/carbonarea", "w")
    if not os.path.exists(storage + "nodes"):
        os.mkdir(storage + "nodes")


def get_echo_length(echo):
    if os.path.exists(storage + "echo/" + echo):
        echo_length = len(open(storage + "echo/" + echo, "r").read().split("\n")) - 1
    else:
        echo_length = 0
    return echo_length


def get_echocount(echoarea):
    return len(open(storage + "echo/" + echoarea, "r").read().split("\n")) - 1


# noinspection PyUnusedLocal
def save_to_favorites(msgid, msg):
    favorites = []
    if os.path.exists(storage + "echo/favorites"):
        with open(storage + "echo/favorites", "r") as f:
            favorites = f.read().splitlines()

    if msgid not in favorites:
        with open(storage + "echo/favorites", "a") as f:
            f.write(msgid + "\n")
        return True
    else:
        return False


def get_echo_msgids(echo):
    if not os.path.exists(storage + "echo/" + echo):
        return []
    with open(storage + "echo/" + echo, "r") as f:
        return f.read().splitlines()


def get_carbonarea():
    if not os.path.exists(storage + "echo/carbonarea"):
        return []
    with open(storage + "echo/carbonarea", "r") as f:
        return list(filter(lambda item: len(item) == 20,
                           f.read().splitlines()))


# noinspection PyUnusedLocal
def add_to_carbonarea(msgid, msgbody):
    with codecs.open(storage + "echo/carbonarea", "a", "utf-8") as f:
        f.write(msgid + "\n")


# noinspection PyUnusedLocal
def save_message(raw, node, to):
    carbonarea = get_carbonarea()
    for msg in raw:
        msgid = msg[0]
        msgbody = msg[1]
        with codecs.open(storage + "echo/" + msgbody[1], "a", "utf-8") as f:
            f.write(msgid + "\n")
        with codecs.open(storage + "msg/" + msgid, "w", "utf-8") as f:
            f.write("\n".join(msgbody))
        if to:
            for name in to:
                if name in msgbody[5] and msgid not in carbonarea:
                    add_to_carbonarea(msgid, msgbody)


def get_favorites_list():
    if not os.path.exists(storage + "echo/favorites"):
        return []

    with open(storage + "echo/favorites", "r") as f:
        return list(filter(lambda it: len(it) == 20, f.read().splitlines()))


def remove_from_favorites(msgid):
    favorites_list = get_favorites_list()
    favorites_list.remove(msgid)
    with open(storage + "echo/favorites", "w") as f:
        f.write("\n".join(favorites_list))


def remove_echoarea(echoarea):
    msgids = []
    f_echo = storage + "echo/%s" % echoarea
    if os.path.exists(f_echo):
        with open(f_echo, "r") as f:
            msgids = f.read().splitlines()
    #
    for msgid in msgids:
        msgid = storage + "msg/%s" % msgid
        if os.path.exists(msgid):
            os.remove(msgid)
    #
    if os.path.exists(f_echo):
        os.remove(f_echo)


def get_msg_list_data(echoarea, msgids=None):
    msgids = msgids or get_echo_msgids(echoarea)
    echo_msgs = defaultdict(list)
    for msgid in msgids:
        with codecs.open(storage + "msg/" + msgid, "r", "utf-8") as f:
            header = []
            last_line = ""
            while len(header) < 6:
                buf = f.read(200)
                lines = buf.split("\n")
                lines[0] = last_line + lines[0]
                if len(lines) > 1:
                    header.extend(lines[0:-1])
                last_line = lines[-1]
            #
            if (header[1] == echoarea
                    or echoarea in (None, "carbonarea", "favorites")):
                echo_msgs[header[1]].append([
                    msgid,
                    header[3],
                    header[6],
                    time.strftime("%Y.%m.%d", time.gmtime(int(header[2]))),
                ])
    lst = []
    for k in sorted(echo_msgs.keys()):
        lst += echo_msgs[k]
    return lst


# noinspection PyUnusedLocal
def read_msg(msgid, echoarea):
    if not os.path.exists(storage + "msg/" + msgid) or not msgid:
        return ["", "", "", "", "", "", "", "", "Сообщение отсутствует в базе"], 0

    with open(storage + "msg/" + msgid, "r") as f:
        msg = f.read().split("\n")
    size = os.stat(storage + "msg/" + msgid).st_size
    return msg, size


def find_msg(msgid):
    for echo in os.listdir(storage + "echo/"):
        if echo in ("carbonarea", "favorites"):
            continue  # not echo

        with codecs.open(storage + "echo/" + echo, "r", "utf-8") as f:
            exists = next(filter(lambda it: it.strip() == msgid,
                                 f.read().split("\n")), None)
            if exists:
                return read_msg(msgid, echo)
    return ["", "", "", "", "", "", "", "", "Сообщение отсутствует в базе"], 0


def find_subj_msgids(echoarea, subj):
    # type: (str, str) -> List[str]
    if subj.startswith("Re:"):
        subj = subj[3:].lstrip()

    echo_msgids = get_echo_msgids(echoarea)
    thread_msgids = []
    for msgid in echo_msgids:
        with open(storage + "msg/" + msgid, "r") as f:
            msg = f.read().split("\n")
            if msg[6].endswith(subj):
                thread_msgids.append(msgid)
    return thread_msgids


def get_node_features(node):  # type: (str) -> Optional[List[str]]
    features = storage + "nodes/" + node + ".x-features"
    if not os.path.exists(features):
        return None  #

    with open(features, "r") as f:
        return list(filter(None, map(lambda it: it.strip(),
                                     f.read().splitlines())))


def save_node_features(node, features):  # type: (str, List[str]) -> None
    x_features = storage + "nodes/" + node + ".x-features"
    with open(x_features, "w") as f:
        f.write("\n".join(features))


def get_node_echo_counts(node):  # type: (str) -> Optional[dict[str, int]]
    x_counts = storage + "nodes/" + node + ".x-counts"
    if not os.path.exists(x_counts):
        return None  #

    with open(x_counts, "r") as f:
        echo_counts = list(filter(None, map(lambda it: it.strip().split(":"),
                                            f.read().splitlines())))
        return {echo[0]: int(echo[1]) for echo in echo_counts}


def save_node_echo_counts(node, echo_counts):  # type: (str, dict[str, int]) -> None
    ec = ["%s:%s\n" % (echo, str(count))
          for echo, count in echo_counts.items()]
    x_counts = storage + "nodes/" + node + ".x-counts"
    with open(x_counts, "w") as f:
        f.writelines(ec)
