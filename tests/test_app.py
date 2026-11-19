import pytest

import app as app_module
import rules


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    monkeypatch.setattr(app_module, "lobby", app_module.Lobby())
    monkeypatch.setattr(app_module, "sessions", {})


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


RELAYED_CHAT = {
    "topic": "state-dispatch",
    "message": {"action": {"channel": "chat", "type": "NEW_MESSAGE", "payload": "hi"}, "signature": "s"},
}


def end_turn(client, moves):
    client.emit("message", {"topic": "end-turn", "message": {"moves": moves}})


def dispatches(client):
    """The (channel, type, payload) of every state-dispatch the client received."""
    result = []
    for m in client.get_received():
        if m["name"] == "message" and payload(m)["topic"] == "state-dispatch":
            action = payload(m)["message"]["action"]
            result.append((action["channel"], action["type"], action["payload"]))
    return result


def current_game():
    (game, _), = {id(g): (g, p) for g, p in app_module.sessions.values()}.values()
    return game


def test_chat_is_relayed_to_opponent_only():
    a, b = connect("abc"), connect("abc")
    other = connect("xyz")
    a.get_received(), b.get_received()

    a.emit("message", RELAYED_CHAT)

    assert [payload(m) for m in b.get_received() if m["name"] == "message"] == [RELAYED_CHAT]
    assert a.get_received() == []
    assert other.get_received() == []


@pytest.mark.parametrize("channel", ["board/pieces", "game/turn", "game/winner", "menu/endturn", "unknown"])
def test_clients_cannot_relay_authoritative_channels(channel):
    a, b = connect("abc"), connect("abc")
    a.get_received(), b.get_received()

    action = {"channel": channel, "type": "SET", "payload": [0] * 192}
    a.emit("message", {"topic": "state-dispatch", "message": {"action": action, "signature": "s"}})

    assert b.get_received() == []


@pytest.mark.parametrize("message", [
    {"topic": "game-ready", "message": {"assignment": "1"}},
    {"topic": "opponent-disconnected", "message": {}},
    {"topic": "state-dispatch", "message": None},
    {"topic": "state-dispatch", "message": {"action": "nope"}},
    {"topic": "end-turn"},
    "junk",
    None,
    42,
    [],
])
def test_spoofed_and_malformed_messages_are_dropped_without_crashing(message):
    a, b = connect("abc"), connect("abc")
    a.get_received(), b.get_received()

    a.emit("message", message)

    assert b.get_received() == []
    assert a.is_connected() and b.is_connected()


def test_end_turn_broadcasts_the_new_state_to_both_players():
    a, b = connect("abc"), connect("abc")
    a.get_received(), b.get_received()

    end_turn(a, [9 * 12 + 4, 8 * 12 + 4])

    expected_board = list(rules.INITIAL_BOARD)
    expected_board[9 * 12 + 4], expected_board[8 * 12 + 4] = 0, 1
    expected = [
        ("board/pieces", "SET", expected_board),
        ("game/turn", "SET", "2"),
        ("board/turn/move", "RESET", None),
    ]
    assert dispatches(a) == expected
    assert dispatches(b) == expected


def test_end_turn_signs_server_actions_so_clients_do_not_echo_them():
    a, b = connect("abc"), connect("abc")
    a.get_received(), b.get_received()

    end_turn(a, [9 * 12 + 4, 8 * 12 + 4])

    for m in b.get_received():
        assert payload(m)["message"]["signature"] == "server"


def test_turns_alternate_between_players():
    a, b = connect("abc"), connect("abc")
    end_turn(a, [9 * 12 + 4, 8 * 12 + 4])
    a.get_received(), b.get_received()

    end_turn(b, [6 * 12 + 4, 7 * 12 + 4])

    assert [d[:2] for d in dispatches(a)] == [("board/pieces", "SET"), ("game/turn", "SET"), ("board/turn/move", "RESET")]
    assert current_game().turn == "1"


def test_out_of_turn_move_is_rejected_to_sender_only():
    a, b = connect("abc"), connect("abc")
    a.get_received(), b.get_received()

    end_turn(b, [6 * 12 + 4, 7 * 12 + 4])

    assert topics(b) == [("move-rejected", {"error": "It is not your turn"})]
    assert a.get_received() == []
    assert current_game().board == list(rules.INITIAL_BOARD)


def test_illegal_move_is_rejected_and_state_is_unchanged():
    a, b = connect("abc"), connect("abc")
    a.get_received(), b.get_received()

    end_turn(a, [9 * 12 + 4, 5 * 12 + 4])

    assert [t for t, _ in topics(a)] == ["move-rejected"]
    assert b.get_received() == []
    assert current_game().turn == "1"


@pytest.mark.parametrize("moves", [None, "abc", [1], [-1, 5], [1.5, 2], {"a": 1}])
def test_malformed_end_turn_is_rejected(moves):
    a, b = connect("abc"), connect("abc")
    a.get_received(), b.get_received()

    end_turn(a, moves)

    assert [t for t, _ in topics(a)] == ["move-rejected"]
    assert a.is_connected()


def test_winning_turn_announces_the_winner_before_resetting_the_move():
    a, b = connect("abc"), connect("abc")
    game = current_game()
    game.board = [0] * 192
    game.board[9 * 12 + 4], game.board[8 * 12 + 4] = 1, 3
    a.get_received(), b.get_received()

    end_turn(a, [9 * 12 + 4, 7 * 12 + 4])

    assert [(c, t) for c, t, _ in dispatches(b)] == [
        ("board/pieces", "SET"),
        ("game/turn", "SET"),
        ("game/winner", "FINISH"),
        ("board/turn/move", "RESET"),
    ]
    assert dispatches(a)[2] == ("game/winner", "FINISH", {"winner": "1"})

    end_turn(b, [0, 1])
    assert topics(b) == [("move-rejected", {"error": "The game is over"})]


def test_disconnect_clears_the_session():
    a, b = connect("abc"), connect("abc")
    assert len(app_module.sessions) == 2
    a.disconnect()
    assert app_module.sessions == {}
    b.get_received()


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
