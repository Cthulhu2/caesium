import base64
import os
import shutil
from pathlib import Path

import pytest


def test_init_aio():
    import api.aio as api
    api.init("test2.aio")
    assert api.storage == "test2.aio/"
    assert Path("test2.aio").is_dir()
    os.removedirs(Path("test2.aio"))


def test_init_ait():
    import api.ait as api
    api.init("test2.ait")
    assert api.storage == "test2.ait/"
    assert Path("test2.ait").is_dir()
    os.removedirs(Path("test2.ait"))


def test_init_sqlite():
    import api.sqlite as api
    api.init("test2.db")
    assert api.c
    assert api.con
    assert Path("test2.db").is_file()
    os.remove(Path("test2.db"))


def test_init_txt():
    import api.txt as api
    api.init("test2.txt")
    assert api.storage == "test2.txt/"
    assert Path("test2.txt").is_dir()
    shutil.rmtree("test2.txt")


@pytest.fixture
def api(storage):
    if storage == "aio":
        import api.aio as api
        api.init("test.aio")
    elif storage == "ait":
        import api.ait as api
        api.init("test.ait")
    elif storage == "sqlite":
        import api.sqlite as api
        api.init("test.db")
    elif storage == "txt":
        import api.txt as api
        api.init("test.txt")
    else:
        raise ValueError("Unknown API")
    clean(api)
    try:
        yield api
    finally:
        clean(api)


def clean(api):
    api.remove_echoarea("test.local")
    api.remove_echoarea("carbonarea")
    api.remove_echoarea("favorites")
    api.remove_echoarea("idec.talks")


# noinspection PyTestParametrized
@pytest.mark.parametrize("storage", ["aio", "ait", "sqlite", "txt"])
def test_get_echo_length(api):
    assert api.get_echo_length("ring2.global") == 4
    assert api.get_echo_length("test.local") == 0


# noinspection PyTestParametrized
@pytest.mark.parametrize("storage", ["aio", "ait", "sqlite", "txt"])
def test_save_messages(api):
    assert api.get_echo_length("test.local") == 0

    msg1 = ["ii/ok", "test.local", "0", "admin", "node,1", "All", "Subj", "", "Msg1", "Row2"]
    msg2 = ["ii/ok", "test.local", "0", "admin", "node,1", "All", "Subj", "", "Msg2", "Row2"]

    api.save_message([("11", msg1), ("22", msg2)], "node", "user")
    assert api.get_echo_length("test.local") == 2
    #
    msg, size = api.read_msg("11", "test.local")
    assert msg == msg1

    msg, size = api.read_msg("22", "test.local")
    assert msg == msg2

    msgids = api.get_echo_msgids("test.local")
    assert msgids == ["11", "22"]

    data = api.get_msg_list_data("test.local")
    assert data == [['11', 'admin', 'Subj', '1970.01.01'],
                    ["22", "admin", "Subj", "1970.01.01"]]


# noinspection PyTestParametrized
@pytest.mark.parametrize("storage", ["aio", "ait", "sqlite", "txt"])
def test_add_to_carbonarea(api):
    assert api.get_echo_length("test.local") == 0

    msg1 = ["ii/ok", "test.local", "0", "admin", "node,1", "All", "Subj", "", "Msg1", "Row2"]
    msg2 = ["ii/ok", "test.local", "0", "admin", "node,1", "user", "Subj", "", "Msg2", "Row2"]

    api.save_message([("1" * 20, msg1), ("2" * 20, msg2)], "node", ["user"])
    assert api.get_echo_length("test.local") == 2
    assert api.get_carbonarea() == ["2" * 20]
    #
    msg, size = api.read_msg("1" * 20, "test.local")
    assert msg == msg1

    msg, size = api.read_msg("2" * 20, "carbonarea")
    assert msg == msg2

    data = api.get_msg_list_data("carbonarea")
    assert data == [["2" * 20, "admin", "Subj", "1970.01.01"]]


# noinspection PyTestParametrized
@pytest.mark.parametrize("storage", ["aio", "ait", "sqlite", "txt"])
def test_save_favorites(api):
    assert not api.get_favorites_list()

    msg1 = ["ii/ok", "test.local", "0", "admin", "node,1", "All", "Subj", "", "Msg1", "Row2"]
    msg2 = ["ii/ok", "test.local", "0", "admin", "node,1", "user", "Subj", "", "Msg2", "Row2"]
    api.save_message([("1" * 20, msg1), ("2" * 20, msg2)], "node", ["user"])
    api.save_to_favorites("2" * 20, msg2)

    favorites = api.get_favorites_list()
    assert favorites == ["2" * 20]
    msg, size = api.read_msg("2" * 20, "favorites")
    assert msg == msg2

    data = api.get_msg_list_data("favorites")
    assert data == [["2" * 20, "admin", "Subj", "1970.01.01"]]

    api.remove_from_favorites("2" * 20)
    assert not api.get_favorites_list()

    data = api.get_msg_list_data("favorites")
    assert data == []


# noinspection PyTestParametrized
@pytest.mark.parametrize("storage", ["aio", "ait", "sqlite", "txt"])
def test_remove_from_favorites(api):
    msg1 = ["ii/ok", "test.local", "0", "admin", "node,1", "All", "Subj", "", "Msg1", "Row2"]
    msg2 = ["ii/ok", "test.local", "0", "admin", "node,1", "user", "Subj", "", "Msg2", "Row2"]
    api.save_message([("1" * 20, msg1), ("2" * 20, msg2)], "node", ["user"])
    api.save_to_favorites("1" * 20, msg1)
    api.save_to_favorites("2" * 20, msg2)
    #
    api.remove_from_favorites("1" * 20)
    #
    favorites = api.get_favorites_list()
    assert favorites == ["2" * 20]
    msg, size = api.read_msg("2" * 20, "favorites")
    assert msg == msg2


# noinspection PyTestParametrized
@pytest.mark.parametrize("storage", ["aio", "ait", "sqlite", "txt"])
def test_non_printable(api):
    msgid = "nFaF9Z8R81USSRIE7YUF"
    msgbody = ("aWkvb2sKaWRlYy50YWxrcwoxNzI5NjA0OTcyCnJldm9sdGVj"
               "aAp0Z2ksMTUKQWxsCkZpcnN0IHRlc3QKChwVLyASGBQePwo=")
    msgbody = base64.b64decode(msgbody).decode("utf8").split("\n")
    #
    api.save_message([(msgid, msgbody)], "", "")
    #
    assert api.get_echo_length("idec.talks") == 1
    assert api.get_echo_msgids("idec.talks") == [msgid]
    #
    msg, _ = api.read_msg(msgid, "idec.talks")
    assert msg == msgbody
    #
    api.save_to_favorites(msgid, msgbody)
    assert api.get_favorites_list() == [msgid]
    msg, _ = api.read_msg(msgid, "favorites")
    assert msg == msgbody

    data = api.get_msg_list_data("idec.talks")
    assert data == [[msgid, "revoltech", "First test", "2024.10.22"]]
