import os
import re
import webbrowser


class Node:
    nodename = "untitled node"
    echoareas = []
    node = ""
    auth = ""
    to = []
    archive = []
    stat = []

    def __init__(self, nodename):
        self.nodename = nodename


def ensure_exists():
    if not os.path.exists("caesium.cfg"):
        with open("caesium.def.cfg", "r") as def_cfg:
            with open("caesium.cfg", "w") as cfg:
                cfg.write(def_cfg.read())


class Config:
    browser = webbrowser
    editor = "nano"
    oldquote = False
    splash = True
    theme = "default"
    db = "ait"
    keys = "default"
    twit = ""

    def reset(self):
        self.editor = "nano"
        self.oldquote = False
        self.db = "ait"

    def load(self, lines):
        shrink_spaces = re.compile(r"(\s\s+|\t+)")
        for line in lines:
            param = shrink_spaces.sub(" ", line.strip()).split(" ", maxsplit=2)
            if param[0] == "editor":
                self.editor = " ".join(param[1:])
            elif param[0] == "theme":
                self.theme = param[1]
            elif param[0] == "nosplash":
                self.splash = False
            elif param[0] == "oldquote":
                self.oldquote = True
            elif param[0] == "db":
                self.db = param[1]
            elif param[0] == "browser":
                self.browser = webbrowser.GenericBrowser(param[1])
            elif param[0] == "twit":
                self.twit = param[1].split(",")
            elif param[0] == "keys":
                self.keys = param[1]
