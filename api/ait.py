# coding=utf-8
import codecs
import os
import time

storage = "ait/"


def init(directory="ait/"):
    global storage
    storage = directory
    if not storage.endswith("/"):
        storage += "/"
    if not os.path.exists(storage):
        os.mkdir(storage)


def get_echo_length(echo):
    if os.path.exists(storage + echo + ".iat"):
        echo_length = sum(1 for _ in open(storage + echo + ".iat", "r", newline="\n"))
    else:
        echo_length = 0
    return echo_length


def save_to_favorites(msgid, msg):
    favorites = []
    if os.path.exists(storage + "favorites.mat"):
        with open(storage + "favorites.mat", "r") as f:
            for line in f.read().splitlines():
                favorites.append(line.split(":")[0])
    if msgid not in favorites:
        with codecs.open(storage + "favorites.iat", "a", "utf-8") as f:
            f.write(msgid + "\n")
        with codecs.open(storage + "favorites.mat", "a", "utf-8") as f:
            f.write(msgid + ":" + chr(15).join(msg) + "\n")
        return True
    else:
        return False


def get_echo_msgids(echo):
    if os.path.exists(storage + echo + ".iat"):
        with codecs.open(storage + echo + ".iat", "r", "utf-8") as f:
            return list(filter(lambda line: line, f.read().splitlines()))
    return []


def get_carbonarea():
    if os.path.exists(storage + "carbonarea.iat"):
        with open(storage + "carbonarea.iat", "r") as f:
            return list(filter(lambda line: line, f.read().splitlines()))
    return []


def add_to_carbonarea(msgid, msgbody):
    with codecs.open(storage + "carbonarea.iat", "a", "utf-8") as f:
        f.write(msgid + "\n")
    with codecs.open(storage + "carbonarea.mat", "a", "utf-8") as f:
        f.write(msgid + ":" + chr(15).join(msgbody) + "\n")


# noinspection PyUnusedLocal
def save_message(raw, node, to):
    for msg in raw:
        msgid = msg[0]
        msgbody = msg[1]
        with codecs.open(storage + msgbody[1] + ".iat", "a", "utf-8") as f:
            f.write(msgid + "\n")
        with codecs.open(storage + msgbody[1] + ".mat", "a", "utf-8") as f:
            f.write(msgid + ":" + chr(15).join(msgbody) + "\n")
        if to:
            carbonarea = get_carbonarea()
            for name in to:
                if name in msgbody[5] and msgid not in carbonarea:
                    add_to_carbonarea(msgid, msgbody)


def get_favorites_list():
    if not os.path.exists(storage + "favorites.iat"):
        return []
    with codecs.open(storage + "favorites.iat", "r", "utf-8") as f:
        return f.read().splitlines()


def remove_from_favorites(msgid):
    favorites_list = get_favorites_list()
    favorites = []
    favorites_index = []
    for item in favorites_list:
        if not item.startswith(msgid):
            favorites.append(item)
            favorites_index.append(item.split(":")[0])
    with codecs.open(storage + "favorites.iat", "w", "utf-8") as f:
        f.write("\n".join(favorites_index))
    with codecs.open(storage + "favorites.mat", "w", "utf-8") as f:
        f.write("\n".join(favorites))


def remove_echoarea(echoarea):
    if os.path.exists(storage + "%s.iat" % echoarea):
        os.remove(storage + "%s.iat" % echoarea)
    if os.path.exists(storage + "%s.mat" % echoarea):
        os.remove(storage + "%s.mat" % echoarea)


def get_msg_list_data(echoarea):
    lst = []
    with codecs.open(storage + "%s.mat" % echoarea, "r", "utf-8") as f:
        for msg in filter(lambda line: line, f.read().split("\n")):
            rawmsg = msg.split(chr(15))
            lst.append([
                rawmsg[0].split(":")[0],
                rawmsg[3],
                rawmsg[6],
                time.strftime("%Y.%m.%d", time.gmtime(int(rawmsg[2]))),
            ])
    return lst


def read_msg(msgid, echoarea):
    if not os.path.exists(storage + echoarea + ".mat") or not msgid:
        return ["", "", "", "", "", "", "", "", "Сообщение отсутствует в базе"], "0b"

    with codecs.open(storage + echoarea + ".mat", "r", "utf-8") as f:
        index = list(filter(lambda i: i.startswith(msgid), f.read().split("\n")))
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
