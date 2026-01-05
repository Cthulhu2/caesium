import os
from pathlib import Path

import pytest

from tests import assertListEquals


def test_init():
    import api.ait as api
    api.init("test2.ait")
    assert api.storage == "test2.ait/"
    assert Path("test2.ait").is_dir()
    os.removedirs(Path("test2.ait"))


@pytest.fixture
def api():
    import api.ait as api
    api.init("test.ait")
    return api


@pytest.fixture
def test_local(api):
    api.remove_echoarea("test.local")
    api.remove_echoarea("carbonarea")
    api.remove_echoarea("favorites")


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

    api.save_message([("11", msg1), ("22", msg2)], "node", ["user"])
    assert api.get_echo_length("test.local") == 2
    assertListEquals(api.get_carbonarea(), ["22"])
    #
    msg, size = api.read_msg("11", "test.local")
    assertListEquals(msg, msg1)

    msg, size = api.read_msg("22", "carbonarea")
    assertListEquals(msg, msg2)


def test_save_favorites(api, test_local):
    assert not api.get_favorites_list()

    msg1 = ["ii/ok", "test.local", "0", "admin", "node,1", "All", "Subj", "Msg1", "Row2"]
    msg2 = ["ii/ok", "test.local", "0", "admin", "node,1", "user", "Subj", "Msg2", "Row2"]

    api.save_message([("11", msg1), ("22", msg2)], "node", ["user"])
    api.save_to_favorites("22", msg2)

    favorites = api.get_favorites_list()
    assertListEquals(favorites, ["22"])
    msg, size = api.read_msg("22", "favorites")
    assertListEquals(msg, msg2)

    api.remove_from_favorites("22")
    assert not api.get_favorites_list()
