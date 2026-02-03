# coding=utf-8
import sqlite3
import time
from typing import Optional, List

from core import FEAT_FEATURES, FEAT_X_C

con = None  # type: Optional[sqlite3.Connection]
c = None  # type: Optional[sqlite3.Cursor]


def init(db="idec.db"):
    global con, c
    con = sqlite3.connect(db)
    c = con.cursor()

    # Create database
    c.execute("""CREATE TABLE IF NOT EXISTS msg(
        id         INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE NOT NULL,
        msgid      TEXT,
        favorites  INTEGER DEFAULT 0,
        carbonarea INTEGER DEFAULT 0,
        tags       TEXT,
        echoarea   TEXT,
        time       INTEGER,
        fr         TEXT,
        addr       TEXT,
        t          TEXT,
        subject    TEXT,
        body       TEXT);""")
    c.execute("CREATE INDEX IF NOT EXISTS msgid    ON 'msg' ('msgid');")
    c.execute("CREATE INDEX IF NOT EXISTS echoarea ON 'msg' ('echoarea');")
    c.execute("CREATE INDEX IF NOT EXISTS time     ON 'msg' ('time');")
    c.execute("CREATE INDEX IF NOT EXISTS subject  ON 'msg' ('subject');")
    c.execute("CREATE INDEX IF NOT EXISTS body     ON 'msg' ('body');")

    c.execute("""CREATE TABLE IF NOT EXISTS node_feature(
        node        TEXT,
        feature     TEXT,
        response    TEXT,
        PRIMARY KEY (node, feature));""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_node_feature"
              " ON node_feature (node, feature);")

    con.commit()


def get_echo_length(echo):
    row = c.execute("SELECT COUNT(1) FROM msg WHERE echoarea = ?;",
                    (echo,)).fetchone()
    return row[0]


def get_echocount(echo):
    return get_echo_length(echo)


# noinspection PyUnusedLocal
def save_to_favorites(msgid, msg):
    favorites = c.execute("SELECT COUNT(1) FROM msg WHERE msgid = ? AND favorites = 1",
                          (msgid,)).fetchone()[0]
    if favorites == 0:
        c.execute("UPDATE msg SET favorites = 1 WHERE msgid = ?;", (msgid,))
        con.commit()
        return True
    else:
        return False


def get_echo_msgids(echo):
    msgids = []
    for row in c.execute("SELECT msgid FROM msg WHERE echoarea = ? ORDER BY id;",
                         (echo,)):
        if row[0]:
            msgids.append(row[0])
    return msgids


def get_carbonarea():
    msgids = []
    for row in c.execute("SELECT msgid FROM msg WHERE carbonarea = 1 ORDER BY id"):
        msgids.append(row[0])
    return msgids


# noinspection PyUnusedLocal
def add_to_carbonarea(msgid, msgbody):
    c.execute("UPDATE msg SET carbonarea = 1 WHERE msgid = ?;",
              (msgid,))
    con.commit()


# noinspection PyUnusedLocal
def save_message(raw, node, to):
    for msg in raw:
        msgid = msg[0]
        msgbody = msg[1]
        c.execute(
            "INSERT INTO msg ("
            " msgid, tags, echoarea, time, fr, addr,"
            " t, subject, body"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (msgid, msgbody[0], msgbody[1], msgbody[2], msgbody[3], msgbody[4],
             msgbody[5], msgbody[6], "\n".join(msgbody[7:])))
    con.commit()
    for msg in raw:
        msgid = msg[0]
        msgbody = msg[1]
        if to:
            carbonarea = get_carbonarea()
            for name in to:
                if name in msgbody[5] and msgid not in carbonarea:
                    add_to_carbonarea(msgid, msgbody)


def get_favorites_list():
    msgids = []
    for row in c.execute("SELECT msgid FROM msg WHERE favorites = 1;"):
        msgids.append(row[0])
    return msgids


def remove_from_favorites(msgid):
    c.execute("UPDATE msg SET favorites = 0 WHERE msgid = ?;", (msgid,))
    con.commit()


def remove_echoarea(echoarea):
    c.execute("DELETE FROM msg WHERE echoarea = ?;", (echoarea,))
    con.commit()


def get_msg_list_data(echoarea, msgids=None):
    if not msgids:
        if echoarea == "favorites":
            rows = c.execute("SELECT msgid, fr, subject, time FROM msg"
                             " WHERE favorites = 1 ORDER BY id;")
        elif echoarea == "carbonarea":
            rows = c.execute("SELECT msgid, fr, subject, time FROM msg"
                             " WHERE carbonarea = 1 ORDER BY id;")
        else:
            rows = c.execute("SELECT msgid, fr, subject, time"
                             " FROM msg WHERE echoarea = ? ORDER BY id;",
                             (echoarea,))
    else:
        args = list(msgids)
        echo_clause = ""
        if echoarea == "favorites":
            echo_clause = " AND favorites = 1 "
        elif echoarea == "carbonarea":
            echo_clause = " AND carbonarea = 1 "
        elif echoarea:
            echo_clause = " AND echoarea = ? "
            args.append(echoarea)
        echo_order = ""
        if not echoarea:
            echo_order = "echoarea, "
        rows = c.execute("SELECT msgid, fr, subject, time FROM msg"
                         " WHERE msgid IN (%s) %s ORDER BY %s id;"
                         % (",".join("?" * len(msgids)), echo_clause, echo_order),
                         args)
    return list(map(
        lambda r: [r[0], r[1], r[2], time.strftime("%Y.%m.%d",
                                                   time.gmtime(int(r[3])))],
        rows))


# noinspection PyUnusedLocal
def read_msg(msgid, echoarea):
    row = c.execute("SELECT tags, echoarea, time, fr, addr, t, subject, body"
                    " FROM msg WHERE msgid = ?;",
                    (msgid,)).fetchone()
    if not row:
        return ["", "", "", "", "", "", "", "", "Сообщение отсутствует в базе"], 0
    msg = "\n".join((row[0], row[1], str(row[2]), row[3],
                     row[4], row[5], row[6], row[7]))

    size = len(msg.encode("utf-8"))
    return msg.split("\n"), size


def find_msg(msgid):
    return read_msg(msgid, None)


def find_subj_msgids(echoarea, subj):  # type: (str, str) -> List[str]
    if subj.startswith("Re: "):
        subj = subj[4:]
    elif subj.startswith("Re:"):
        subj = subj[3:]
    subjRe = "Re:" + subj
    subjReSpace = "Re: " + subj

    rows = c.execute("SELECT msgid FROM msg"
                     " WHERE echoarea = ?"
                     "   AND (subject = ? OR subject = ? OR subject = ?)"
                     " LIMIT 1000;",
                     (echoarea, subj, subjRe, subjReSpace))
    return list(map(lambda r: r[0], rows))


def get_node_features(node):  # type: (str) -> Optional[List[str]]
    features = c.execute("SELECT response FROM node_feature"
                         " WHERE node = ? AND feature = ?;",
                         (node, FEAT_FEATURES)).fetchone()
    if features:
        return list(filter(None, map(lambda it: it.strip(),
                                     features[0].splitlines())))
    return None


def save_node_features(node, features):  # type: (str, List[str]) -> None
    features = "\n".join(features)
    c.execute("DELETE FROM node_feature WHERE node = ? AND feature = ?;",
              (node, FEAT_FEATURES))
    c.execute("INSERT INTO node_feature (node, feature, response) VALUES (?, ?, ?);",
              (node, FEAT_FEATURES, features))
    con.commit()


def get_node_echo_counts(node):  # type: (str) -> Optional[dict[str, int]]
    ec = c.execute("SELECT response FROM node_feature"
                   " WHERE node = ? AND feature = ?;",
                   (node, FEAT_X_C)).fetchone()
    if ec:
        echo_counts = list(filter(None, map(lambda it: it.strip().split(":"),
                                            ec[0].splitlines())))
        return {echo[0]: int(echo[1]) for echo in echo_counts}
    return None


def save_node_echo_counts(node, echo_counts):  # type: (str, dict[str, int]) -> None
    ec = ["%s:%s\n" % (echo, str(count))
          for echo, count in echo_counts.items()]
    ec = "".join(ec)

    c.execute("DELETE FROM node_feature WHERE node = ? AND feature = ?;",
              (node, FEAT_X_C))
    c.execute("INSERT INTO node_feature (node, feature, response) VALUES (?, ?, ?);",
              (node, FEAT_X_C, ec))
    con.commit()
