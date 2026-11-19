import pytest

import app as app_module


@pytest.fixture(autouse=True)
def fresh_lobby(monkeypatch):
    monkeypatch.setattr(app_module, "lobby", app_module.Lobby())


def connect(code=None):
    headers = {"Game-Code": code} if code else {}
    return app_module.socketio.test_client(app_module.app, headers=headers)


def payload(m):
    # the test client unwraps single-argument events
    args = m["args"]
    return args[0] if isinstance(args, list) else args


def topics(client):
    return [
        (payload(m)["topic"], payload(m)["message"])
        for m in client.get_received()
        if m["name"] == "message"
    ]


def errors(client):
    return [payload(m)["error"] for m in client.get_received() if m["name"] == "error"]


def test_missing_game_code_is_rejected():
    assert not connect().is_connected()


def test_first_player_gets_no_error_and_waits():
    a = connect("abc")
    assert a.is_connected()
    assert a.get_received() == []


def test_two_players_are_assigned_and_ready():
    a = connect("abc")
    b = connect("abc")
    assert topics(a) == [("game-ready", {"assignment": "1"})]
    assert topics(b) == [("game-ready", {"assignment": "2"})]


def test_third_player_is_refused():
    a, b = connect("abc"), connect("abc")
    a.get_received(), b.get_received()
    c = connect("abc")
    assert not c.is_connected()
    assert a.get_received() == [] and b.get_received() == []


def test_messages_are_relayed_to_opponent_only():
    a, b = connect("abc"), connect("abc")
    other = connect("xyz")
    a.get_received(), b.get_received()

    sent = {"topic": "state-dispatch", "message": {"x": 1}}
    a.emit("message", sent)

    assert [payload(m) for m in b.get_received() if m["name"] == "message"] == [sent]
    assert a.get_received() == []
    assert other.get_received() == []


def test_disconnect_notifies_opponent_with_well_formed_message():
    a, b = connect("abc"), connect("abc")
    a.get_received(), b.get_received()
    a.disconnect()
    assert topics(b) == [("opponent-disconnected", {})]


def test_message_after_opponent_left_does_not_crash():
    a, b = connect("abc"), connect("abc")
    a.disconnect()
    b.get_received()
    b.emit("message", {"topic": "t", "message": {}})
    assert errors(b) == ["No opponent connected"]
    assert b.is_connected()


def test_waiting_player_disconnect_frees_code():
    a = connect("abc")
    a.disconnect()
    b, c = connect("abc"), connect("abc")
    assert topics(b) == [("game-ready", {"assignment": "1"})]
    assert topics(c) == [("game-ready", {"assignment": "2"})]
