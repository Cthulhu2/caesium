import base64
import os
from pathlib import Path

import pytest

from tests import assertListEquals


def test_init():
    import api.aio as api
    api.init("test2.aio")
    assert api.storage == "test2.aio/"
    assert Path("test2.aio").is_dir()
    os.removedirs(Path("test2.aio"))


@pytest.fixture
def api():
    import api.aio as api
    api.init("test.aio")
    return api


@pytest.fixture
def test_local(api):
    api.remove_echoarea("test.local")
    api.remove_echoarea("carbonarea")
    api.remove_echoarea("favorites")
    api.remove_echoarea("idec.talks")


def test_get_echo_length(api, test_local):
    assert api.get_echo_length("ring2.global") == 4
    assert api.get_echo_length("test.local") == 0


def test_save_messages(api, test_local):
    assert api.get_echo_length("test.local") == 0

    msg1 = ["ii/ok", "test.local", "0", "admin", "node,1", "All", "Subj", "Msg1", "Row2"]
    msg2 = ["ii/ok", "test.local", "0", "admin", "node,1", "All", "Subj", "Msg2", "Row2"]

    api.save_message([("11", msg1), ("22", msg2)], "node", "user")
    assert api.get_echo_length("test.local") == 2
    #
    msg, size = api.read_msg("11", "test.local")
    assert len(msg) == len(msg1)
    assert all([a == b for a, b in zip(msg, msg1)])

    msg, size = api.read_msg("22", "test.local")
    assert len(msg) == len(msg2)
    assert all([a == b for a, b in zip(msg, msg2)])

    msgids = api.get_echo_msgids("test.local")
    assertListEquals(msgids, ["11", "22"])


def test_add_to_carbonarea(api, test_local):
    assert api.get_echo_length("test.local") == 0

    msg1 = ["ii/ok", "test.local", "0", "admin", "node,1", "All", "Subj", "Msg1", "Row2"]
    msg2 = ["ii/ok", "test.local", "0", "admin", "node,1", "user", "Subj", "Msg2", "Row2"]

    api.save_message([("1" * 20, msg1), ("2" * 20, msg2)], "node", ["user"])
    assert api.get_echo_length("test.local") == 2
    assertListEquals(api.get_carbonarea(), ["2" * 20])
    #
    msg, size = api.read_msg("1" * 20, "test.local")
    assertListEquals(msg, msg1)

    msg, size = api.read_msg("2" * 20, "carbonarea")
    assertListEquals(msg, msg2)


def test_save_favorites(api, test_local):
    assert not api.get_favorites_list()

    msg1 = ["ii/ok", "test.local", "0", "admin", "node,1", "All", "Subj", "Msg1", "Row2"]
    msg2 = ["ii/ok", "test.local", "0", "admin", "node,1", "user", "Subj", "Msg2", "Row2"]

    api.save_message([("1" * 20, msg1), ("2" * 20, msg2)], "node", ["user"])
    api.save_to_favorites("2" * 20, msg2)

    favorites = api.get_favorites_list()
    assertListEquals(favorites, ["2" * 20])
    msg, size = api.read_msg("2" * 20, "favorites")
    assertListEquals(msg, msg2)

    api.remove_from_favorites("2" * 20)
    assert not api.get_favorites_list()


def test_non_printable(api, test_local):
    msgid = "nFaF9Z8R81USSRIE7YUF"
    msgbody = ("aWkvb2sKaWRlYy50YWxrcwoxNzI5NjA0OTcyCnJldm9sdGVj"
               "aAp0Z2ksMTUKQWxsCkZpcnN0IHRlc3QKChwVLyASGBQePwo=")
    msgbody = base64.b64decode(msgbody).decode("utf8").split("\n")
    #
    api.save_message([(msgid, msgbody)], "", "")
    #
    assert api.get_echo_length("idec.talks") == 1
    assertListEquals(api.get_echo_msgids("idec.talks"), [msgid])
    #
    msg, _ = api.read_msg(msgid, "idec.talks")
    assertListEquals(msgbody, msg)
    #
    api.save_to_favorites(msgid, msgbody)
    assertListEquals([msgid], api.get_favorites_list())
    msg, _ = api.read_msg(msgid, "favorites")
    assertListEquals(msgbody, msg)
