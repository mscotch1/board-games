import types

import pytest

import app as app_module
import rules
from registry import Registry
from rules import BLACK, WHITE
from store import MemoryStore
from variants import CAMELOT

COLS = CAMELOT.cols


def sq(row, col):
    return row * COLS + col


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    monkeypatch.setattr(app_module, "registry", Registry(MemoryStore()))


def connect(code="abc", side=None, token=None):
    auth = {}
    if code is not None:
        auth["code"] = code
    if side is not None:
        auth["side"] = side
    if token is not None:
        auth["token"] = token
    return app_module.socketio.test_client(app_module.app, auth=auth)


def payload(m):
    # the test client unwraps single-argument events
    args = m["args"]
    return args[0] if isinstance(args, list) else args


def raw_messages(client):
    """The (topic, message) of every message the client received."""
    return [(payload(m)["topic"], payload(m)["message"]) for m in client.get_received() if m["name"] == "message"]


def messages(client):
    """Like raw_messages, but leaving out the \"waiting\" a creator gets on arriving."""
    return [(topic, message) for topic, message in raw_messages(client) if topic != "waiting"]


def errors(client):
    return [payload(m)["error"] for m in client.get_received() if m["name"] == "error"]


def pair(creator_side=WHITE, code="abc"):
    """Connect two players; returns (creator, joiner) with their initial messages drained."""
    creator = connect(code, creator_side)
    joiner = connect(code)
    creator.get_received(), joiner.get_received()
    return creator, joiner


def record(code="abc"):
    return {r.code: r for r in app_module.registry.records()}[code]


def current_game(code="abc"):
    return record(code).game


def end_turn(client, moves):
    client.emit("message", {"topic": "end-turn", "message": {"moves": moves}})


# --- connecting -------------------------------------------------------------


@pytest.mark.parametrize("code", [None, "", "   ", 123, ["abc"], "x" * 65])
def test_missing_or_bad_game_code_is_refused(code):
    auth = {} if code is None else {"code": code}
    assert not app_module.socketio.test_client(app_module.app, auth=auth).is_connected()


def test_connecting_without_auth_is_refused():
    assert not app_module.socketio.test_client(app_module.app).is_connected()


def test_first_player_waits_and_is_given_a_token():
    a = connect()
    assert a.is_connected()
    (topic, message), = raw_messages(a)
    assert topic == "waiting"
    assert isinstance(message["token"], str) and len(message["token"]) >= 16


def test_two_players_get_game_ready_with_the_full_state():
    a, b = connect(side=WHITE), connect()
    (topic_a, ready_a), = messages(a)
    (topic_b, ready_b), = messages(b)

    assert topic_a == topic_b == "game-ready"
    assert ready_a["side"] == WHITE and ready_b["side"] == BLACK
    assert ready_a["state"] == ready_b["state"]

    state = ready_a["state"]
    assert state["board"] == list(CAMELOT.initial)
    assert state["turn"] == WHITE and state["winner"] is None
    assert state["legal"]


@pytest.mark.parametrize("requested", [WHITE, BLACK])
def test_the_creator_gets_the_side_they_asked_for(requested):
    a, b = connect(side=requested), connect()
    assert messages(a)[0][1]["side"] == requested
    assert messages(b)[0][1]["side"] == rules.other(requested)


@pytest.mark.parametrize("side", [None, "random", "purple", 3])
def test_other_requests_for_a_side_mean_random(monkeypatch, side):
    monkeypatch.setattr(app_module.registry, "_rng", types.SimpleNamespace(choice=lambda options: BLACK))
    a, b = connect(side=side), connect()
    assert messages(a)[0][1]["side"] == BLACK
    assert messages(b)[0][1]["side"] == WHITE


def test_the_joiners_requested_side_is_ignored():
    a, b = connect(side=WHITE), connect(side=WHITE)
    assert messages(a)[0][1]["side"] == WHITE
    assert messages(b)[0][1]["side"] == BLACK


def test_third_player_is_refused():
    a, b = pair()
    assert not connect().is_connected()
    assert a.get_received() == [] and b.get_received() == []


def test_the_creators_side_request_is_kept_with_the_game():
    connect(side=BLACK)
    assert record("abc").creator_side == BLACK


# --- relayed messages -------------------------------------------------------


def test_chat_goes_to_the_opponent_only():
    a, b = pair()
    other = connect("xyz")
    a.emit("message", {"topic": "chat", "message": {"text": "  hello  "}})
    assert messages(b) == [("chat", {"text": "hello"})]
    assert a.get_received() == [] and messages(other) == []


def test_chat_is_trimmed_and_limited():
    a, b = pair()
    a.emit("message", {"topic": "chat", "message": {"text": "x" * 2000}})
    assert len(messages(b)[0][1]["text"]) == app_module.MAX_CHAT_LENGTH


@pytest.mark.parametrize("text", ["", "   ", None, 5, ["hi"], {"a": 1}])
def test_empty_or_non_text_chat_is_dropped(text):
    a, b = pair()
    a.emit("message", {"topic": "chat", "message": {"text": text}})
    assert b.get_received() == []


def test_hover_and_preview_are_relayed():
    a, b = pair()
    a.emit("message", {"topic": "hover", "message": {"index": 40}})
    a.emit("message", {"topic": "hover", "message": {"index": None}})
    a.emit("message", {"topic": "preview", "message": {"moves": [112, 100]}})
    a.emit("message", {"topic": "preview", "message": {"moves": []}})
    assert messages(b) == [
        ("opponent-hover", {"index": 40}),
        ("opponent-hover", {"index": None}),
        ("opponent-preview", {"moves": [112, 100]}),
        ("opponent-preview", {"moves": []}),
    ]


@pytest.mark.parametrize("message", [
    {"topic": "hover", "message": {"index": -1}},
    {"topic": "hover", "message": {"index": 192}},
    {"topic": "hover", "message": {"index": "5"}},
    {"topic": "hover", "message": {"index": True}},
    {"topic": "preview", "message": {"moves": "nope"}},
    {"topic": "preview", "message": {"moves": [1, -2]}},
    {"topic": "preview", "message": {"moves": [1.5]}},
    {"topic": "preview", "message": {"moves": list(range(100))}},
    {"topic": "preview", "message": None},
    {"topic": "game-ready", "message": {"side": WHITE}},
    {"topic": "game-state", "message": {"state": {}}},
    {"topic": "opponent-disconnected", "message": {}},
    {"topic": "state-dispatch", "message": {"action": {"channel": "board/pieces"}}},
    {"topic": "end-turn"},
    "junk",
    None,
    42,
    [],
])
def test_spoofed_and_malformed_messages_are_dropped_without_crashing(message):
    a, b = pair()
    a.emit("message", message)
    assert [t for t, _ in messages(b)] == []
    assert a.is_connected() and b.is_connected()


# --- turns ------------------------------------------------------------------


def test_end_turn_sends_the_new_state_to_both_players():
    white, black = pair(WHITE)
    end_turn(white, [sq(9, 4), sq(8, 4)])

    (topic_w, update_w), = messages(white)
    (topic_b, update_b), = messages(black)
    assert topic_w == topic_b == "game-state"
    assert update_w == update_b

    state = update_w["state"]
    assert state["board"][sq(8, 4)] == 1 and state["board"][sq(9, 4)] == 0
    assert state["turn"] == BLACK
    assert state["lastTurn"]["moves"] == [sq(9, 4), sq(8, 4)]


def test_the_black_creator_waits_for_white_to_move():
    black, white = pair(BLACK)
    end_turn(black, [sq(6, 4), sq(7, 4)])
    assert [t for t, _ in messages(black)] == ["move-rejected"]

    end_turn(white, [sq(9, 4), sq(8, 4)])
    assert messages(black)[0][0] == "game-state"


def test_turns_alternate_between_players():
    white, black = pair(WHITE)
    end_turn(white, [sq(10, 2), sq(11, 2)])
    end_turn(black, [sq(6, 4), sq(7, 4)])
    assert [t for t, _ in messages(white)] == ["game-state", "game-state"]
    assert current_game().turn == WHITE


def test_out_of_turn_move_is_rejected_to_the_sender_only():
    white, black = pair(WHITE)
    end_turn(black, [sq(6, 4), sq(7, 4)])
    assert messages(black) == [("move-rejected", {"error": "It is not your turn"})]
    assert white.get_received() == []
    assert current_game().board == list(CAMELOT.initial)


def test_illegal_move_is_rejected_and_nothing_changes():
    white, black = pair(WHITE)
    end_turn(white, [sq(9, 4), sq(5, 4)])
    assert [t for t, _ in messages(white)] == ["move-rejected"]
    assert black.get_received() == []
    assert current_game().turn == WHITE


def test_skipping_a_mandatory_capture_is_rejected():
    white, black = pair(WHITE)
    game = current_game()
    game.board = [0] * 192
    game.board[sq(9, 4)], game.board[sq(8, 4)], game.board[sq(12, 2)] = 1, 3, 1
    game._legal = rules.legal_turns(game.variant, game.board, WHITE)

    end_turn(white, [sq(12, 2), sq(11, 2)])
    assert "must capture" in messages(white)[0][1]["error"]

    end_turn(white, [sq(9, 4), sq(7, 4)])
    assert messages(white)[0][0] == "game-state"


@pytest.mark.parametrize("moves", [None, "abc", [1], [-1, 5], [1.5, 2], {"a": 1}])
def test_malformed_end_turn_is_rejected(moves):
    white, black = pair(WHITE)
    end_turn(white, moves)
    assert [t for t, _ in messages(white)] == ["move-rejected"]
    assert white.is_connected()


def test_winning_turn_reports_the_winner_and_ends_the_game():
    white, black = pair(WHITE)
    game = current_game()
    game.board = [0] * 192
    game.board[sq(9, 4)], game.board[sq(8, 4)], game.board[sq(12, 2)] = 1, 3, 1
    game._legal = rules.legal_turns(game.variant, game.board, WHITE)

    end_turn(white, [sq(9, 4), sq(7, 4)])

    for client in (white, black):
        state = messages(client)[0][1]["state"]
        assert (state["winner"], state["winReason"]) == (WHITE, "capture")
        assert state["legal"] == []

    end_turn(black, [0, 1])
    assert messages(black) == [("move-rejected", {"error": "The game is over"})]


# --- leaving ----------------------------------------------------------------


def test_disconnecting_marks_the_player_away_but_keeps_the_game():
    a, b = pair()
    a.disconnect()
    assert messages(b) == [("opponent-status", {"connected": False})]
    assert current_game().over is False
    assert b.is_connected()


def test_a_player_can_keep_playing_while_their_opponent_is_away():
    white, black = pair(WHITE)
    black.disconnect()
    white.get_received()
    end_turn(white, [sq(10, 2), sq(11, 2)])
    assert [t for t, _ in messages(white)] == ["game-state"]
    assert current_game().turn == BLACK


def test_chat_while_the_opponent_is_away_is_kept_without_an_error():
    a, b = pair()
    a.disconnect()
    b.get_received()
    b.emit("message", {"topic": "chat", "message": {"text": "hello?"}})
    assert b.get_received() == []
    assert record("abc").chat == [{"side": BLACK, "text": "hello?"}]


def test_a_waiting_creator_who_leaves_keeps_their_game_open():
    a = connect(side=BLACK)
    a.disconnect()
    assert record("abc").status == "waiting"


# --- serving the client -----------------------------------------------------


@pytest.fixture
def static_dir(tmp_path, monkeypatch):
    (tmp_path / "games" / "camelot").mkdir(parents=True)
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("landing")
    (tmp_path / "games" / "camelot" / "index.html").write_text("camelot")
    (tmp_path / "assets" / "app-abc123.js").write_text("console.log(1)")
    (tmp_path.parent / "secret.txt").write_text("secret")
    monkeypatch.setitem(app_module.app.config, "STATIC_DIR", str(tmp_path))
    return tmp_path


def test_serves_the_landing_page_and_game_pages(static_dir):
    client = app_module.app.test_client()
    assert client.get("/").data == b"landing"
    assert client.get("/index.html").data == b"landing"
    assert client.get("/games/camelot/").data == b"camelot"
    assert client.get("/games/camelot/index.html").data == b"camelot"


def test_directory_without_a_trailing_slash_redirects(static_dir):
    response = app_module.app.test_client().get("/games/camelot")
    assert response.status_code in (301, 302, 307, 308)
    assert response.headers["Location"].endswith("/games/camelot/")


def test_hashed_assets_are_cached_but_pages_are_not(static_dir):
    client = app_module.app.test_client()
    asset = client.get("/assets/app-abc123.js")
    assert "max-age=31536000" in asset.headers["Cache-Control"]
    assert "max-age=31536000" not in (client.get("/").headers.get("Cache-Control") or "")


@pytest.mark.parametrize("url", ["/nope.html", "/games/nope/", "/../secret.txt", "/..%2fsecret.txt", "/assets/../../secret.txt"])
def test_missing_files_and_traversal_are_404(static_dir, url):
    assert app_module.app.test_client().get(url).status_code == 404


def test_healthz():
    assert app_module.app.test_client().get("/healthz").data == b"ok"


@pytest.mark.parametrize("value, expected", [
    (None, None),
    ("", None),
    ("*", "*"),
    ("https://a.example", ["https://a.example"]),
    ("https://a.example, https://b.example ,", ["https://a.example", "https://b.example"]),
])
def test_allowed_origins(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", value)
    assert app_module.allowed_origins() == expected


# --- refusal reasons --------------------------------------------------------
# The browser only sees why it was refused if the exception is python-socketio's
# own, so these call the handler directly and check what it raises.


def refusal(auth):
    from socketio.exceptions import ConnectionRefusedError as SocketIORefusal

    with app_module.app.test_request_context():
        app_module.request.sid = "new-player"
        with pytest.raises(SocketIORefusal) as raised:
            app_module.handle_connect(auth)
    return raised.value.error_args


def test_refusing_a_missing_code_tells_the_client_why():
    assert refusal({}) == {"message": "Missing game code", "data": {"code": "missing-code"}}
    assert refusal(None)["message"] == "Missing game code"


def test_refusing_a_full_game_tells_the_client_why():
    pair(code="full-game")
    assert refusal({"code": "full-game"}) == {"message": "Game already full", "data": {"code": "full"}}


# --- choosing a variant -----------------------------------------------------


def connect_with(variant, code="abc", side=None):
    auth = {"code": code, "variant": variant}
    if side:
        auth["side"] = side
    return app_module.socketio.test_client(app_module.app, auth=auth)


def ready_state(client):
    (topic, message), = messages(client)
    assert topic == "game-ready"
    return message["state"]


def test_games_are_camelot_unless_the_creator_asks_for_another():
    a, b = connect(), connect()
    assert ready_state(a)["variant"] == "camelot"
    assert ready_state(b)["variant"] == "camelot"


def test_the_creator_can_ask_for_cam():
    a, b = connect_with("cam"), connect()
    state_a, state_b = ready_state(a), ready_state(b)
    assert state_a == state_b
    assert (state_a["variant"], state_a["variantName"]) == ("cam", "Cam")
    assert (state_a["rows"], state_a["cols"]) == (13, 7)
    assert sum(1 for p in state_a["board"] if p) == 14
    assert current_game().variant.key == "cam"


def test_whoever_joins_plays_the_creators_variant():
    a, b = connect_with("cam"), connect_with("camelot")
    assert ready_state(a)["variant"] == ready_state(b)["variant"] == "cam"


def test_a_joiner_asking_for_cam_gets_the_creators_camelot_game():
    a, b = connect_with("camelot"), connect_with("cam")
    assert ready_state(b)["variant"] == "camelot"


@pytest.mark.parametrize("variant", ["checkers", "", "CAM", 3, ["cam"], {"cam": 1}])
def test_unknown_variants_are_refused(variant):
    assert not connect_with(variant).is_connected()
    assert app_module.registry.records() == []


def test_the_unknown_variant_refusal_says_why():
    from socketio.exceptions import ConnectionRefusedError as SocketIORefusal

    with app_module.app.test_request_context():
        app_module.request.sid = "new-player"
        with pytest.raises(SocketIORefusal) as raised:
            app_module.handle_connect({"code": "abc", "variant": "checkers"})
    assert raised.value.error_args == {"message": "Unknown game variant", "data": {"code": "unknown-variant"}}


def test_a_cam_game_is_played_with_cam_rules():
    white, black = connect_with("cam", side=WHITE), connect()
    white.get_received(), black.get_received()

    from variants import cam_square

    end_turn(white, [cam_square("B5"), cam_square("B6")])
    (topic, update), = messages(black)
    assert topic == "game-state"
    assert update["state"]["variant"] == "cam"
    assert update["state"]["board"][cam_square("B6")] == 1


def test_hover_and_preview_are_checked_against_the_games_own_board():
    # index 100 is on the Camelot board but off the 91-square Cam board
    a, b = connect_with("cam"), connect()
    a.get_received(), b.get_received()
    a.emit("message", {"topic": "hover", "message": {"index": 100}})
    a.emit("message", {"topic": "preview", "message": {"moves": [1, 100]}})
    assert b.get_received() == []

    a.emit("message", {"topic": "hover", "message": {"index": 90}})
    assert messages(b) == [("opponent-hover", {"index": 90})]

    c, d = pair(code="camelot-game")
    c.emit("message", {"topic": "hover", "message": {"index": 100}})
    assert messages(d) == [("opponent-hover", {"index": 100})]


# --- draws ------------------------------------------------------------------


def draw_action(client, topic, **body):
    client.emit("message", {"topic": topic, "message": body})


def state_of(client):
    updates = [m for t, m in messages(client) if t == "game-state"]
    return updates[-1]["state"]


def test_a_draw_offer_reaches_both_players_in_the_state():
    a, b = pair()
    draw_action(a, "offer-draw")
    offer_seen_by_a, offer_seen_by_b = state_of(a)["drawOffer"], state_of(b)["drawOffer"]
    assert offer_seen_by_a == offer_seen_by_b
    assert offer_seen_by_a in ("white", "black")
    assert current_game().draw_offer is not None


def test_accepting_a_draw_ends_the_game_for_both():
    white, black = pair(WHITE)
    draw_action(white, "offer-draw")
    white.get_received(), black.get_received()

    draw_action(black, "respond-draw", accept=True)
    for client in (white, black):
        state = state_of(client)
        assert state["draw"] == "agreed" and state["winner"] is None
        assert state["legal"] == [] and state["drawOffer"] is None

    end_turn(white, [sq(10, 2), sq(11, 2)])
    assert messages(white) == [("move-rejected", {"error": "The game is over"})]


def test_declining_a_draw_tells_the_offerer():
    white, black = pair(WHITE)
    draw_action(white, "offer-draw")
    white.get_received(), black.get_received()

    draw_action(black, "respond-draw", accept=False)
    assert [t for t, _ in messages(white)] == ["game-state", "draw-declined"]
    assert current_game().draw_offer is None and not current_game().over


@pytest.mark.parametrize("accept", ["yes", 1, None, "true"])
def test_only_a_real_true_accepts_a_draw(accept):
    white, black = pair(WHITE)
    draw_action(white, "offer-draw")
    draw_action(black, "respond-draw", accept=accept)
    assert not current_game().over


def test_answering_your_own_offer_or_a_missing_one_is_rejected():
    white, black = pair(WHITE)
    draw_action(black, "respond-draw", accept=True)
    assert [t for t, _ in messages(black)] == ["draw-rejected"]

    draw_action(white, "offer-draw")
    white.get_received(), black.get_received()
    draw_action(white, "respond-draw", accept=True)
    assert messages(white) == [("draw-rejected", {"error": "There is no draw offer to answer"})]
    assert black.get_received() == []


def test_claiming_a_draw_needs_grounds():
    white, black = pair(WHITE)
    draw_action(white, "claim-draw")
    assert messages(white) == [("draw-rejected", {"error": "There is nothing to claim yet"})]
    assert black.get_received() == []


def test_the_fifty_move_rule_can_be_claimed_over_the_socket():
    white, black = pair(WHITE)
    current_game().plies_without_progress = 100
    draw_action(black, "claim-draw")
    for client in (white, black):
        assert state_of(client)["draw"] == "fifty-moves"


def test_a_move_withdraws_a_pending_offer_in_the_next_state():
    white, black = pair(WHITE)
    draw_action(black, "offer-draw")
    white.get_received(), black.get_received()
    end_turn(white, [sq(10, 2), sq(11, 2)])
    assert state_of(black)["drawOffer"] is None


def test_cam_refuses_draw_requests():
    white, black = connect_with("cam"), connect()
    white.get_received(), black.get_received()
    for topic in ("offer-draw", "claim-draw", "respond-draw"):
        draw_action(white, topic, accept=True)
    errors_seen = [m["error"] for t, m in messages(white) if t == "draw-rejected"]
    assert errors_seen == ["Cam has no draws"] * 3
    assert black.get_received() == []
