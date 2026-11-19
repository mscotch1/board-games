import time

import pytest

import app as app_module
from registry import Registry
from rules import BLACK, WHITE
from store import MemoryStore
from test_app import messages, payload


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    monkeypatch.setattr(app_module, "registry", Registry(MemoryStore()))
    monkeypatch.setattr(app_module, "COMPUTER_PAUSE", 0)
    app_module.computer_busy.clear()


def play_against_computer(side=WHITE, level="easy", variant="cam", code="bot1", **extra):
    auth = {"code": code, "side": side, "variant": variant, "computer": level, **extra}
    client = app_module.socketio.test_client(app_module.app, auth=auth)
    return client


def wait_for(client, topic, timeout=15):
    """Collect messages until one with `topic` arrives (the computer moves on its own thread)."""
    seen = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        seen.extend(messages(client))
        for t, m in seen:
            if t == topic:
                return m, seen
        time.sleep(0.05)
    raise AssertionError(f"no {topic!r} arrived; got {[t for t, _ in seen]}")


def first_move(state):
    turn = state["legal"][0]
    return turn["moves"]


def test_a_game_against_the_computer_starts_at_once():
    client = play_against_computer()
    ready, _ = wait_for(client, "game-ready")
    assert ready["side"] == WHITE
    assert ready["computer"] == "easy"
    assert ready["opponentConnected"] is True
    assert ready["state"]["turn"] == WHITE
    client.disconnect()


def test_the_computer_answers_a_move():
    client = play_against_computer()
    ready, _ = wait_for(client, "game-ready")
    client.emit("message", {"topic": "end-turn", "message": {"moves": first_move(ready["state"])}})
    state = None
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and not (state and state["turn"] == WHITE and state["lastTurn"]["player"] == BLACK):
        for t, m in messages(client):
            if t == "game-state":
                state = m["state"]
        time.sleep(0.05)
    assert state and state["lastTurn"]["player"] == BLACK, "the computer never replied"
    client.disconnect()


def test_the_computer_moves_first_when_it_is_white():
    client = play_against_computer(side=BLACK)
    ready, seen = wait_for(client, "game-ready")
    assert ready["side"] == BLACK
    state, _ = wait_for(client, "game-state")
    assert state["state"]["lastTurn"]["player"] == WHITE
    assert state["state"]["turn"] == BLACK
    client.disconnect()


def test_an_unknown_level_is_refused():
    client = app_module.socketio.test_client(app_module.app, auth={"code": "x1", "computer": "impossible"})
    assert not client.is_connected()


def test_a_player_cannot_add_a_computer_to_someone_elses_game():
    human = app_module.socketio.test_client(app_module.app, auth={"code": "x2", "side": WHITE})
    human.get_received()
    joiner = app_module.socketio.test_client(app_module.app, auth={"code": "x2", "computer": "hard"})
    ready = [m for t, m in messages(joiner) if t == "game-ready"][0]
    assert ready["computer"] is None


def test_the_computer_declines_a_draw_when_it_is_not_losing():
    client = play_against_computer(variant="camelot")
    ready, _ = wait_for(client, "game-ready")
    client.emit("message", {"topic": "offer-draw", "message": {}})
    _, seen = wait_for(client, "draw-declined")
    assert any(t == "draw-declined" for t, _ in seen)
    client.disconnect()


def test_resigning_ends_the_game_and_the_computer_stops():
    client = play_against_computer()
    wait_for(client, "game-ready")
    client.emit("message", {"topic": "resign", "message": {}})
    state, _ = wait_for(client, "game-state")
    assert state["state"]["winner"] == BLACK
    client.disconnect()


def test_the_computer_game_survives_the_player_coming_back():
    client = play_against_computer(side=BLACK)
    ready, _ = wait_for(client, "game-ready")
    token = ready["token"]
    client.disconnect()
    again = app_module.socketio.test_client(
        app_module.app, auth={"code": "bot1", "token": token, "resume": True}
    )
    back, _ = wait_for(again, "game-ready")
    assert back["side"] == BLACK and back["computer"] == "easy"
    again.disconnect()


def test_the_computer_seat_is_saved_with_the_game():
    client = play_against_computer()
    wait_for(client, "game-ready")
    record = app_module.registry._get("bot1")
    from registry import Record

    loaded = Record.from_dict(record.to_dict())
    assert loaded.bot == "easy" and loaded.bot_token == record.bot_token
    client.disconnect()
