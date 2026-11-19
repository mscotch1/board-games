import pytest

from lobby import JoinResult, Lobby


def test_first_player_waits():
    lobby = Lobby()
    assert lobby.join("abc", "a") == (JoinResult.WAITING, None)
    assert lobby.opponent("a") is None


def test_second_player_pairs():
    lobby = Lobby()
    lobby.join("abc", "a")
    assert lobby.join("abc", "b") == (JoinResult.PAIRED, "a")
    assert lobby.opponent("a") == "b"
    assert lobby.opponent("b") == "a"


def test_third_player_is_rejected_and_not_registered():
    lobby = Lobby()
    lobby.join("abc", "a")
    lobby.join("abc", "b")
    assert lobby.join("abc", "c") == (JoinResult.FULL, None)
    assert lobby.opponent("c") is None
    assert lobby.leave("c") is None
    assert lobby.opponent("a") == "b"


def test_different_codes_do_not_pair():
    lobby = Lobby()
    lobby.join("one", "a")
    assert lobby.join("two", "b") == (JoinResult.WAITING, None)


def test_joining_twice_raises():
    lobby = Lobby()
    lobby.join("abc", "a")
    with pytest.raises(ValueError):
        lobby.join("xyz", "a")


def test_waiting_player_leaving_frees_code():
    lobby = Lobby()
    lobby.join("abc", "a")
    assert lobby.leave("a") is None
    assert lobby.join("abc", "b") == (JoinResult.WAITING, None)


def test_leaving_unpairs_both_and_returns_opponent():
    lobby = Lobby()
    lobby.join("abc", "a")
    lobby.join("abc", "b")
    assert lobby.leave("a") == "b"
    assert lobby.opponent("b") is None
    # the survivor leaving later has nobody left to notify
    assert lobby.leave("b") is None


def test_code_can_be_reused_after_game_ends():
    lobby = Lobby()
    lobby.join("abc", "a")
    lobby.join("abc", "b")
    lobby.leave("a")
    lobby.leave("b")
    assert lobby.join("abc", "c") == (JoinResult.WAITING, None)
    assert lobby.join("abc", "d") == (JoinResult.PAIRED, "c")


def test_leave_unknown_sid():
    assert Lobby().leave("nobody") is None
