import dataclasses
import os
import re
import webbrowser
from typing import List, Optional

CONFIG_FILEPATH = "caesium.cfg"


def ensure_exists():
    if not os.path.exists(CONFIG_FILEPATH):
        with open("caesium.def.cfg", "r") as def_cfg:
            with open(CONFIG_FILEPATH, "w") as cfg:
                cfg.write(def_cfg.read())


@dataclasses.dataclass
class Echo:
    name: str
    desc: str
    noSync: bool

    def __gt__(self, other):
        if other:
            return self.name > other.name
        return False

    def __lt__(self, other):
        if other:
            return self.name < other.name
        return False


ECHO_OUT = Echo("out", "Исходящие", False)
ECHO_FAVORITES = Echo("favorites", "Избранные сообщения", True)
ECHO_CARBON = Echo("carbonarea", "Карбонка", True)


@dataclasses.dataclass
class Node:
    nodename: str = "untitled node"
    echoareas: List[Echo] = dataclasses.field(default_factory=list)
    node: str = ""
    auth: str = ""
    to: List[str] = dataclasses.field(default_factory=list)
    archive: List[Echo] = dataclasses.field(default_factory=list)
    stat: List[Echo] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Config:
    nodes: List[Node] = dataclasses.field(default_factory=list)
    browser = webbrowser
    editor = "nano"
    oldquote = False
    splash = True
    theme = "default"
    db = "ait"
    keys = "default"
    twit: List[str] = dataclasses.field(default_factory=list)

    def reset(self):
        self.nodes.clear()
        self.editor = "nano"
        self.oldquote = False
        self.db = "ait"

    def load(self):
        node = None  # type: Optional[Node]
        shrink_spaces = re.compile(r"(\s\s+|\t+)")
        with open(CONFIG_FILEPATH) as f:
            lines = f.read().splitlines()
        for line in lines:
            param = shrink_spaces.sub(" ", line.strip()).split(" ", maxsplit=2)
            #
            if param[0] == "nodename":
                if node:
                    node.echoareas.sort()
                    self.nodes.append(node)
                node = Node(nodename=" ".join(param[1:]))
            elif param[0] == "node":
                node.node = param[1]
                if not node.node.endswith("/"):
                    node.node += "/"
            elif param[0] == "auth":
                node.auth = param[1]
            elif param[0] == "to":
                node.to = " ".join(param[1:]).split(",")
            elif param[0] == "echo":
                node.echoareas.append(Echo(param[1], "".join(param[2:]), False))
            elif param[0] == "stat":
                node.echoareas.append(Echo(param[1], "".join(param[2:]), True))
            elif param[0] == "archive":
                node.archive.append(Echo(param[1], "".join(param[2:]), True))
            #
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

        node.echoareas.sort()
        self.nodes.append(node)
        for n in self.nodes:
            n.echoareas.insert(0, ECHO_FAVORITES)
            n.echoareas.insert(1, ECHO_CARBON)
