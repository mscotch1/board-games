"""Reloads, dropped connections and server restarts, end to end through the socket handlers."""

import pytest
from socketio.exceptions import ConnectionRefusedError as SocketIORefusal

import app as app_module
from registry import DEFAULT_TTL, Registry
from rules import BLACK, WHITE
from store import SqliteStore
from variants import CAMELOT

COLS = CAMELOT.cols


def sq(row, col):
    return row * COLS + col


@pytest.fixture(autouse=True)
def fresh_registry(monkeypatch):
    from store import MemoryStore

    monkeypatch.setattr(app_module, "registry", Registry(MemoryStore()))


def connect(code="abc", token=None, side=None, variant=None, resume=False):
    auth = {"code": code}
    if token:
        auth["token"] = token
    if resume:
        auth["resume"] = True
    if side:
        auth["side"] = side
    if variant:
        auth["variant"] = variant
    return app_module.socketio.test_client(app_module.app, auth=auth)


def payload(m):
    args = m["args"]
    return args[0] if isinstance(args, list) else args


def messages(client):
    return [(payload(m)["topic"], payload(m)["message"]) for m in client.get_received() if m["name"] == "message"]


def topics(client):
    return [topic for topic, _ in messages(client)]


def record(code="abc"):
    return {r.code: r for r in app_module.registry.records()}[code]


def token(side, code="abc"):
    return record(code).seats[side]


def end_turn(client, moves):
    client.emit("message", {"topic": "end-turn", "message": {"moves": moves}})


def chat(client, text):
    client.emit("message", {"topic": "chat", "message": {"text": text}})


def start(creator_side=WHITE, code="abc", variant=None):
    """Two players, with their opening messages drained. Returns (white, black)."""
    creator = connect(code, side=creator_side, variant=variant)
    joiner = connect(code)
    creator.get_received(), joiner.get_received()
    return (creator, joiner) if creator_side == WHITE else (joiner, creator)


def refusal(auth):
    with app_module.app.test_request_context():
        app_module.request.sid = "new-player"
        with pytest.raises(SocketIORefusal) as raised:
            app_module.handle_connect(auth)
    return raised.value.error_args


# --- a player comes back ----------------------------------------------------


def test_a_returning_player_gets_the_game_as_they_left_it():
    white, black = start()
    end_turn(white, [sq(10, 2), sq(11, 2)])
    chat(white, "your move")
    white.get_received(), black.get_received()
    black.disconnect()

    back = connect(token=token(BLACK))
    (topic, ready), = messages(back)
    assert topic == "game-ready"
    assert ready["side"] == BLACK and ready["token"] == token(BLACK)
    assert ready["state"]["turn"] == BLACK
    assert ready["state"]["lastTurn"]["moves"] == [sq(10, 2), sq(11, 2)]
    assert ready["chat"] == [{"side": WHITE, "text": "your move"}]
    assert ready["opponentConnected"] is True


def test_moves_made_while_away_are_waiting_on_return():
    white, black = start()
    black.disconnect()
    end_turn(white, [sq(10, 2), sq(11, 2)])

    back = connect(token=token(BLACK))
    (_, ready), = messages(back)
    assert ready["state"]["turn"] == BLACK
    end_turn(back, [sq(6, 4), sq(7, 4)])
    assert topics(back) == ["game-state"]


def test_the_opponent_sees_a_player_leave_and_return():
    white, black = start()
    black.disconnect()
    assert messages(white) == [("opponent-status", {"connected": False})]

    connect(token=token(BLACK))
    assert messages(white) == [("opponent-status", {"connected": True})]


def test_the_returning_player_is_told_the_opponent_is_away():
    white, black = start()
    white.disconnect()
    back = connect(token=token(BLACK))
    black.disconnect()
    back2 = connect(token=token(BLACK))
    (_, ready), = messages(back2)
    assert ready["opponentConnected"] is False


def test_a_reconnect_can_be_the_creator_too():
    white, black = start(creator_side=BLACK)
    black.disconnect()
    (_, ready), = messages(connect(token=token(BLACK)))
    assert ready["side"] == BLACK


def test_a_second_tab_shares_the_seat():
    white, black = start()
    tab_two = connect(token=token(BLACK))
    tab_two.get_received()
    assert messages(white) == []  # they were already online, so there is nothing to announce

    end_turn(white, [sq(10, 2), sq(11, 2)])
    assert topics(black) == ["game-state"] and topics(tab_two) == ["game-state"]
    white.get_received()

    black.disconnect()
    assert messages(white) == []  # one tab is still open
    tab_two.disconnect()
    assert messages(white) == [("opponent-status", {"connected": False})]


def test_either_tab_can_play_the_move():
    white, black = start(creator_side=BLACK)  # black is the creator, white is the joiner
    white_tab = connect(token=token(WHITE))
    white_tab.get_received()
    end_turn(white_tab, [sq(10, 2), sq(11, 2)])
    assert topics(black) == ["game-state"]
    assert record().game.turn == BLACK


# --- tokens -----------------------------------------------------------------


def test_the_wrong_or_missing_token_does_not_get_a_seat():
    start()
    fake = "f" * 22
    assert not connect(token=fake).is_connected()  # a stranger with a token: it's a full game
    assert not connect(token=fake, resume=True).is_connected()
    assert not connect().is_connected()
    assert refusal({"code": "abc", "token": fake, "resume": True}) == {
        "message": "That game could not be found. It may have expired.",
        "data": {"code": "not-found"},
    }
    assert refusal({"code": "abc", "token": fake}) == {"message": "Game already full", "data": {"code": "full"}}
    assert refusal({"code": "abc"}) == {"message": "Game already full", "data": {"code": "full"}}


@pytest.mark.parametrize("bad", ["", 5, ["x"], "x" * 129, "short", "has spaces in it, and is long", ("snow" + chr(0x2603) + "man") * 4, True])
def test_malformed_tokens_are_refused(bad):
    assert refusal({"code": "abc", "token": bad})["data"] == {"code": "bad-token"}


def test_tokens_are_secret_from_the_opponent():
    white, black = start()
    white.get_received(), black.get_received()
    connect(token=token(BLACK))
    for _, message in messages(white):
        assert token(BLACK) not in str(message)
    chat(black, "hi")  # no token in anything relayed either
    assert token(BLACK) not in str(messages(white))


def test_a_stale_token_for_a_game_that_never_existed_creates_nothing():
    assert not connect(code="ghost", token="o" * 22, resume=True).is_connected()
    assert app_module.registry.records() == []


def test_a_finished_game_can_still_be_looked_at():
    white, black = start()
    white.emit("message", {"topic": "resign", "message": {}})
    white.get_received(), black.get_received()
    white.disconnect(), black.disconnect()

    (_, ready), = messages(connect(token=token(WHITE)))
    assert ready["state"]["winner"] == BLACK and ready["state"]["winReason"] == "resignation"
    assert not connect().is_connected()  # but nobody new can join


def test_expired_games_cannot_be_resumed():
    start_clock = [1_000.0]
    app_module.registry = Registry(app_module.registry._store, clock=lambda: start_clock[0])
    white, black = start(code="old")
    saved_token = token(WHITE, "old")
    white.disconnect(), black.disconnect()

    start_clock[0] += DEFAULT_TTL["playing"] + 1
    app_module.registry.purge_expired()
    assert not connect(code="old", token=saved_token, resume=True).is_connected()
    assert refusal({"code": "old", "token": saved_token, "resume": True})["data"] == {"code": "not-found"}


# --- a game that is still waiting -------------------------------------------


def test_a_waiting_creator_gets_the_same_token_back():
    creator = connect(side=BLACK)
    (_, first), = [m for m in messages(creator) if m[0] == "waiting"]
    creator.disconnect()

    again = connect(token=first["token"])
    assert messages(again) == [("waiting", {"token": first["token"]})]


def test_the_opponent_can_join_while_the_creator_is_away():
    creator = connect(side=WHITE)
    creator_token = [m for t, m in messages(creator) if t == "waiting"][0]["token"]
    creator.disconnect()

    joiner = connect()
    (_, joiner_ready), = messages(joiner)
    assert joiner_ready["side"] == BLACK and joiner_ready["opponentConnected"] is False

    back = connect(token=creator_token)
    (_, ready), = messages(back)
    assert ready["side"] == WHITE and ready["opponentConnected"] is True
    assert messages(joiner) == [("opponent-status", {"connected": True})]


def test_the_creator_is_told_when_the_opponent_arrives_on_any_tab():
    creator = connect(side=WHITE)
    creator_token = [m for t, m in messages(creator) if t == "waiting"][0]["token"]
    second_tab = connect(token=creator_token)
    second_tab.get_received()

    connect()
    assert topics(creator) == ["game-ready"] and topics(second_tab) == ["game-ready"]


def test_a_creator_can_cancel_and_the_code_can_be_reused():
    creator = connect()
    creator.get_received()
    creator.emit("message", {"topic": "cancel-game", "message": {}})
    assert messages(creator) == [("game-cancelled", {})]
    assert app_module.registry.records() == []
    assert connect().is_connected()


def test_chat_is_refused_until_there_is_an_opponent():
    creator = connect()
    creator.get_received()
    chat(creator, "anyone?")
    assert [m["name"] for m in creator.get_received()] == ["error"]


# --- resigning --------------------------------------------------------------


def test_resigning_ends_the_game_for_both_players():
    white, black = start()
    black.emit("message", {"topic": "resign", "message": {}})
    for client in (white, black):
        (topic, update), = messages(client)
        assert topic == "game-state"
        assert (update["state"]["winner"], update["state"]["winReason"]) == (WHITE, "resignation")
    assert record().status == "finished"


def test_resigning_twice_is_rejected():
    white, black = start()
    white.emit("message", {"topic": "resign", "message": {}})
    white.get_received(), black.get_received()
    black.emit("message", {"topic": "resign", "message": {}})
    assert messages(black) == [("action-rejected", {"error": "The game is over"})]
    assert white.get_received() == []


# --- surviving a restart ----------------------------------------------------


def test_a_server_restart_loses_nothing(tmp_path):
    database = str(tmp_path / "games.sqlite3")
    app_module.registry = Registry(SqliteStore(database))
    white, black = start()
    end_turn(white, [sq(10, 2), sq(11, 2)])
    chat(black, "see you after the restart")
    white_token, black_token = token(WHITE), token(BLACK)
    board_before = record().game.board[:]

    # the process dies: every connection is gone and so is everything in memory
    app_module.registry = Registry(SqliteStore(database))
    assert app_module.registry.records() == []

    back_white = connect(token=white_token)
    (_, ready), = messages(back_white)
    assert ready["state"]["board"] == board_before and ready["state"]["turn"] == BLACK
    assert ready["chat"] == [{"side": BLACK, "text": "see you after the restart"}]
    assert ready["opponentConnected"] is False

    back_black = connect(token=black_token)
    assert messages(back_white) == [("opponent-status", {"connected": True})]
    back_black.get_received()
    end_turn(back_black, [sq(6, 4), sq(7, 4)])
    assert topics(back_white) == ["game-state"]


def test_a_game_waiting_for_an_opponent_survives_a_restart(tmp_path):
    database = str(tmp_path / "games.sqlite3")
    app_module.registry = Registry(SqliteStore(database))
    creator = connect(side=BLACK, variant="cam")
    creator_token = [m for t, m in messages(creator) if t == "waiting"][0]["token"]

    app_module.registry = Registry(SqliteStore(database))
    joiner = connect()
    (_, ready), = messages(joiner)
    assert ready["side"] == WHITE and ready["state"]["variant"] == "cam"

    back = connect(token=creator_token)
    assert messages(back)[0][1]["side"] == BLACK


# --- tokens made by the browser ---------------------------------------------


def test_players_can_bring_their_own_tokens():
    mine, theirs = "m" * 22, "t" * 22
    creator = connect(token=mine, side=WHITE)
    assert messages(creator) == [("waiting", {"token": mine})]
    joiner = connect(token=theirs)
    assert messages(creator)[0][1]["side"] == WHITE
    assert record().seats == {WHITE: mine, BLACK: theirs}


def test_a_creator_who_reconnects_before_hearing_back_is_still_the_creator():
    mine = "m" * 22
    first = connect(token=mine)
    first.disconnect()
    again = connect(token=mine)  # no resume flag: the browser never got an answer the first time
    assert messages(again) == [("waiting", {"token": mine})]
    assert len(app_module.registry.records()) == 1


def test_a_returning_player_is_refused_after_the_game_is_deleted():
    mine = "m" * 22
    connect(token=mine).disconnect()
    app_module.registry.cancel  # exists
    for r in app_module.registry.records():
        app_module.registry._delete(r.code)
    assert not connect(token=mine, resume=True).is_connected()
    assert refusal({"code": "abc", "token": mine, "resume": True})["data"] == {"code": "not-found"}
