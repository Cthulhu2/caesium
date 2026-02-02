import codecs
import os
from typing import List

from core import config

storage = ""


def init(cfg, storage_=""):
    global storage
    storage = storage_
    if storage:
        if not storage.endswith("/"):
            storage += "/"
    if not os.path.exists(storage + "out"):
        os.mkdir(storage + "out")

    for nd in map(directory, cfg.nodes):
        if not os.path.exists(nd):
            os.mkdir(nd)


def directory(node):
    return storage + "out/" + node.nodename + "/"


def get_out_msgids(node, drafts=False):
    # type: (config.Node, bool) -> List[str]
    msgids = []
    node_dir = directory(node)
    if os.path.exists(node_dir):
        if drafts:
            msgids = [f for f in sorted(os.listdir(node_dir))
                      if f.endswith(".draft")]
        else:
            msgids = [f for f in sorted(os.listdir(node_dir))
                      if f.endswith(".out") or f.endswith(".outmsg")]
    return msgids


def read_out_msg(msgid, node):  # type: (str, config.Node) -> (List[str], int)
    node_dir = directory(node)
    with open(node_dir + msgid, "r") as f:
        temp = f.read().splitlines()
    if len(temp) < 8:
        temp += [""] * (8 - len(temp))
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
    size = os.stat(node_dir + msgid).st_size
    return msg, size


def save_out(node, extension):
    with codecs.open("temp", "r", "utf-8") as f:
        new = f.read().strip().replace("\r", "").split("\n")
    if len(new) <= 1:
        os.remove("temp")
    else:
        with codecs.open(outcount(node) + extension, "w", "utf-8") as f:
            f.write("\n".join(new))
        os.remove("temp")


def resave_out(node, filename):
    with codecs.open("temp", "r", "utf-8") as f:
        new = f.read().strip().replace("\r", "").split("\n")
    if len(new) <= 1:
        os.remove("temp")
    else:
        out_dir = directory(node)
        with codecs.open(out_dir + filename, "w", "utf-8") as f:
            f.write("\n".join(new))
        os.remove("temp")


def outcount(node):
    outpath = directory(node)
    num = 0
    for x in os.listdir(outpath):
        s_num = x.split(".", maxsplit=1)[0]
        if s_num.isdigit():
            num = max(num, int(s_num))
    return outpath + "/%s" % str(num + 1).zfill(5)


def get_out_length(node, drafts=False):
    node_dir = directory(node)
    if drafts:
        return len([f for f in os.listdir(node_dir)
                    if f.endswith(".draft")]) - 1
    else:
        return len([f for f in os.listdir(node_dir)
                    if f.endswith(".out") or f.endswith(".outmsg")]) - 1
