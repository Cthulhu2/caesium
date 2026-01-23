# coding=utf-8
import codecs
import os
import time
from typing import Optional, List

storage = "aio/"


def init(directory="aio/"):
    global storage
    storage = directory
    if not storage.endswith("/"):
        storage += "/"
    if not os.path.exists(storage):
        os.mkdir(storage)
    if not os.path.exists(storage + "nodes"):
        os.mkdir(storage + "nodes")


def get_echo_length(echo):
    if os.path.exists(storage + echo + ".aio"):
        with open(storage + echo + ".aio", "r", newline="\n") as f:
            return len(f.readlines())
    return 0


def save_to_favorites(msgid, msg):
    favorites = []
    if os.path.exists(storage + "favorites.aio"):
        with open(storage + "favorites.aio", "r") as f:
            favorites = list(map(lambda it: it.split(":")[0],
                                 filter(lambda it: it, f.read().split("\n"))))
    if msgid not in favorites:
        with codecs.open(storage + "favorites.aio", "a", "utf-8") as f:
            f.write(msgid + ":" + chr(15).join(msg) + "\n")
        return True
    else:
        return False


def get_echo_msgids(echo):
    if not os.path.exists(storage + echo + ".aio"):
        return []

    with codecs.open(storage + echo + ".aio", "r", "utf-8") as f:
        return list(map(lambda it: it.split(":")[0],
                        filter(lambda it: it, f.read().split("\n"))))


def get_carbonarea():
    if not os.path.exists(storage + "carbonarea.aio"):
        return []
    with open(storage + "carbonarea.aio", "r") as f:
        return list(filter(lambda it: len(it) == 20,
                           map(lambda it: it.split(":")[0],
                               filter(lambda it: it, f.read().split("\n")))))


def add_to_carbonarea(msgid, msgbody):
    with codecs.open(storage + "carbonarea.aio", "a", "utf-8") as f:
        f.write(msgid + ":" + chr(15).join(msgbody) + "\n")


# noinspection PyUnusedLocal
def save_message(raw, node, to):
    for msg in raw:
        msgid = msg[0]
        msgbody = msg[1]
        with codecs.open(storage + msgbody[1] + ".aio", "a", "utf-8") as f:
            f.write(msgid + ":" + chr(15).join(msgbody) + "\n")
        if to:
            carbonarea = get_carbonarea()
            for name in to:
                if name in msgbody[5] and msgid not in carbonarea:
                    add_to_carbonarea(msgid, msgbody)


def get_favorites_list():
    if not os.path.exists(storage + "favorites.aio"):
        return []
    with codecs.open(storage + "favorites.aio", "r", "utf-8") as f:
        return list(map(lambda msg: msg.split(":")[0],
                        filter(None, f.read().split("\n"))))


def remove_from_favorites(msgid):
    with codecs.open(storage + "favorites.aio", "r", "utf-8") as f:
        favorites = list(filter(lambda it: it and not it.startswith(msgid + ":"),
                                f.read().split("\n")))
    with codecs.open(storage + "favorites.aio", "w", "utf-8") as f:
        f.write("\n".join(favorites))


def remove_echoarea(echoarea):
    if os.path.exists(storage + "%s.aio" % echoarea):
        os.remove(storage + "%s.aio" % echoarea)


def get_msg_list_data(echoarea):
    with codecs.open(storage + "%s.aio" % echoarea, "r", "utf-8") as f:
        lines = f.read().split("\n")
    lst = []
    for msg in filter(None, lines):
        rawmsg = msg.split(chr(15))
        lst.append([
            rawmsg[0].split(":")[0],
            rawmsg[3],
            rawmsg[6],
            time.strftime("%Y.%m.%d", time.gmtime(int(rawmsg[2]))),
        ])
    return lst


def read_msg(msgid, echoarea):
    if not os.path.exists(storage + echoarea + ".aio") or not msgid:
        return ["", "", "", "", "", "", "", "", "Сообщение отсутствует в базе"], 0

    with codecs.open(storage + echoarea + ".aio", "r", "utf-8") as f:
        index = list(filter(lambda i: i.startswith(msgid),
                            f.read().split("\n")))
    msg = None
    size = 0
    if index:
        msg = ":".join(index[-1].split(":")[1:]).split(chr(15))
    if msg:
        size = len("\n".join(msg).encode("utf-8"))
    return msg, size


def find_msg(msgid):
    for echo in os.listdir(storage):
        if echo in ("carbonarea.aio", "favorites.aio") or not echo.endswith(".aio"):
            continue  # not echo

        with codecs.open(storage + echo, "r", "utf-8") as f:
            index = list(filter(lambda it: it.startswith(msgid + ":"),
                                f.read().split("\n")))
        if index:
            msg = ":".join(index[-1].split(":")[1:]).split(chr(15))
            size = len("\n".join(msg).encode("utf-8"))
            return msg, size
    return ["", "", "", "", "", "", "", "", "Сообщение отсутствует в базе"], 0


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
