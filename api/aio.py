# coding=utf-8
import codecs
import os
import time

storage = "aio/"


def init(directory="aio/"):
    global storage
    storage = directory
    if not storage.endswith("/"):
        storage += "/"
    if not os.path.exists(storage):
        os.mkdir(storage)


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
                                 f.read().splitlines()))
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
                        filter(lambda it: it, f.read().splitlines())))


def get_carbonarea():
    if not os.path.exists(storage + "carbonarea.aio"):
        return []
    with open(storage + "carbonarea.aio", "r") as f:
        return list(filter(lambda it: len(it) == 20,
                           map(lambda it: it.split(":")[0],
                               f.read().splitlines())))


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
        return list(map(lambda msg: msg.split(":")[0], f.read().splitlines()))


def remove_from_favorites(msgid):
    favorites = filter(lambda i: not i.startswith(msgid), get_favorites_list())
    with codecs.open(storage + "favorites.aio", "w", "utf-8") as f:
        f.write("\n".join(favorites))


def remove_echoarea(echoarea):
    if os.path.exists(storage + "%s.aio" % echoarea):
        os.remove(storage + "%s.aio" % echoarea)


def get_msg_list_data(echoarea):
    with codecs.open(storage + "%s.aio" % echoarea, "r", "utf-8") as f:
        lines = f.read().splitlines()
    lst = []
    for msg in filter(lambda line: line, lines):
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
        return ["", "", "", "", "", "", "", "", "Сообщение отсутствует в базе"], "0b"

    with codecs.open(storage + echoarea + ".aio", "r", "utf-8") as f:
        index = list(filter(lambda i: i.startswith(msgid),
                            f.read().splitlines()))
    msg = None
    if index:
        msg = ":".join(index[-1].split(":")[1:]).split(chr(15))
    if msg:
        size = len("\n".join(msg).encode("utf-8"))
    else:
        size = 0
    if size < 1024:
        size = str(size) + " B"
    else:
        size = str(format(size / 1024, ".2f")) + " KB"
    return msg, size
