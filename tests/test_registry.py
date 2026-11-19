import json
import types

import pytest

import rules
from registry import CHAT_LIMIT, DEFAULT_TTL, PURGE_INTERVAL, Record, Refused, Registry
from rules import BLACK, WHITE
from store import MemoryStore
from variants import CAM


class Clock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def store():
    return MemoryStore()


@pytest.fixture
def registry(store, clock):
    return Registry(store, clock=clock, rng=types.SimpleNamespace(choice=lambda options: WHITE))


def start_game(registry, code="abc", creator_side=None, variant_key=None):
    creator = registry.attach("creator-1", code, side=creator_side, variant_key=variant_key)
    joiner = registry.attach("joiner-1", code)
    return creator, joiner


# --- creating and joining ---------------------------------------------------


def test_the_first_connection_creates_a_waiting_game(registry, store):
    attached = registry.attach("s1", "abc", side=BLACK, variant_key="cam")
    assert attached.kind == "waiting" and attached.first_connection
    assert isinstance(attached.token, str) and len(attached.token) >= 16

    record = attached.record
    assert (record.status, record.game, record.variant_key, record.creator_side) == ("waiting", None, "cam", BLACK)
    assert store.meta() == [("abc", "waiting", record.updated_at)]


def test_unknown_variants_and_sides_fall_back_to_defaults(registry):
    record = registry.attach("s1", "abc", side="purple", variant_key="checkers").record
    assert (record.variant_key, record.creator_side) == ("camelot", None)


def test_the_second_connection_joins_and_the_game_starts(registry):
    creator, joiner = start_game(registry, creator_side=BLACK)
    assert joiner.kind == "started" and joiner.first_connection
    assert creator.record is joiner.record
    assert joiner.token != creator.token

    record = joiner.record
    assert record.status == "playing"
    assert record.seats == {BLACK: creator.token, WHITE: joiner.token}
    assert record.game.variant.key == "camelot"


def test_a_random_side_comes_from_the_rng(store, clock):
    registry = Registry(store, clock=clock, rng=types.SimpleNamespace(choice=lambda options: BLACK))
    creator, joiner = start_game(registry)
    assert registry.seat_of(joiner.record, creator.token) == BLACK
    assert registry.seat_of(joiner.record, joiner.token) == WHITE


def test_the_game_uses_the_creators_variant(registry):
    creator, joiner = start_game(registry, variant_key="cam")
    assert joiner.record.game.variant is CAM


def test_a_third_connection_is_refused(registry):
    start_game(registry)
    with pytest.raises(Refused) as refusal:
        registry.attach("s3", "abc")
    assert (refusal.value.message, refusal.value.code) == ("Game already full", "full")


def test_a_finished_game_says_so(registry):
    creator, joiner = start_game(registry)
    joiner.record.game.resign(WHITE)
    with pytest.raises(Refused) as refusal:
        registry.attach("s3", "abc")
    assert refusal.value.code == "finished"


# --- coming back ------------------------------------------------------------


def test_a_returning_player_resumes_with_their_token(registry):
    creator, joiner = start_game(registry)
    registry.detach("joiner-1")

    again = registry.attach("joiner-2", "abc", token=joiner.token)
    assert again.kind == "resumed" and again.first_connection
    assert again.record is joiner.record and again.token == joiner.token


def test_a_waiting_creator_can_come_back(registry):
    first = registry.attach("s1", "abc")
    registry.detach("s1")
    again = registry.attach("s2", "abc", token=first.token)
    assert again.kind == "waiting" and again.record is first.record


def test_a_creator_who_returns_after_the_opponent_joined_is_resumed(registry):
    creator, joiner = start_game(registry)
    assert registry.attach("c2", "abc", token=creator.token).kind == "resumed"


def test_resuming_a_game_that_does_not_exist_is_refused_and_creates_nothing(registry):
    with pytest.raises(Refused) as refusal:
        registry.attach("s1", "nope", token="made-up", resume=True)
    assert refusal.value.code == "not-found"
    assert registry.records() == []


def test_resuming_with_the_wrong_token_is_refused(registry):
    start_game(registry)
    with pytest.raises(Refused) as refusal:
        registry.attach("s3", "abc", token="made-up", resume=True)
    assert refusal.value.code == "not-found"
    assert len(registry.records()) == 1


def test_a_stranger_with_a_token_is_still_just_a_stranger(registry):
    start_game(registry)
    with pytest.raises(Refused) as refusal:
        registry.attach("s3", "abc", token="made-up")
    assert refusal.value.code == "full"


def test_the_token_a_player_brings_becomes_theirs(registry):
    creator = registry.attach("s1", "abc", token="creator-made-this")
    assert (creator.kind, creator.token) == ("waiting", "creator-made-this")
    joiner = registry.attach("s2", "abc", token="joiner-made-this")
    assert (joiner.kind, joiner.token) == ("started", "joiner-made-this")
    assert set(joiner.record.seats.values()) == {"creator-made-this", "joiner-made-this"}


def test_a_player_can_reconnect_before_hearing_back_from_the_server(registry):
    # the connection dropped before the browser learned the game existed: the same token comes again
    first = registry.attach("s1", "abc", token="my-own-token")
    registry.detach("s1")
    again = registry.attach("s2", "abc", token="my-own-token")
    assert again.kind == "waiting" and again.record is first.record
    assert len(registry.records()) == 1  # not a second game, and not joined to itself


def test_one_players_token_does_not_open_another_game(registry):
    start_game(registry, code="one")
    creator_two, _ = start_game(registry, code="two")
    with pytest.raises(Refused):
        registry.attach("s9", "one", token=creator_two.token)


def test_a_player_can_have_several_connections(registry):
    creator, joiner = start_game(registry)
    second = registry.attach("creator-2", "abc", token=creator.token)
    assert second.first_connection is False
    assert registry.sids(creator.record, creator.token) == ["creator-1", "creator-2"]

    assert registry.detach("creator-1").offline is False
    assert registry.online(creator.record, creator.token)
    assert registry.detach("creator-2").offline is True
    assert not registry.online(creator.record, creator.token)


def test_detaching_an_unknown_connection_is_fine(registry):
    assert registry.detach("never-attached") is None


def test_sessions_know_their_seat_and_opponent(registry):
    creator, joiner = start_game(registry, creator_side=WHITE)
    session = registry.session("joiner-1")
    assert (session.seat, session.token) == (BLACK, joiner.token)
    assert registry.opponent_token(session.record, joiner.token) == creator.token
    assert registry.session("nobody") is None

    waiting = registry.attach("w1", "other")
    assert registry.session("w1").seat is None
    assert registry.opponent_token(waiting.record, waiting.token) is None


# --- cancelling -------------------------------------------------------------


def test_a_creator_can_cancel_a_waiting_game(registry, store):
    registry.attach("s1", "abc")
    assert registry.cancel("s1") is True
    assert registry.records() == [] and store.meta() == []
    # the code is free again
    assert registry.attach("s2", "abc").kind == "waiting"


def test_nobody_can_cancel_a_game_that_has_started(registry):
    start_game(registry)
    assert registry.cancel("creator-1") is False
    assert registry.cancel("joiner-1") is False
    assert registry.cancel("stranger") is False
    assert len(registry.records()) == 1


# --- keeping games ----------------------------------------------------------


def test_saving_writes_to_the_store_and_stamps_the_time(registry, store, clock):
    creator, joiner = start_game(registry)
    clock.advance(60)
    registry.save(joiner.record)
    assert joiner.record.updated_at == clock.now
    assert store.meta() == [("abc", "playing", clock.now)]


def test_a_game_survives_a_restart(store, clock):
    first = Registry(store, clock=clock)
    creator, joiner = start_game(first, creator_side=WHITE, variant_key="cam")
    game = joiner.record.game
    game.play_turn(WHITE, list(game.legal_turns[0].moves))
    joiner.record.add_chat(WHITE, "hello")
    first.save(joiner.record)

    second = Registry(store, clock=clock)  # a new process: nothing in memory, only the store
    assert second.records() == []
    back = second.attach("c2", "abc", token=creator.token)
    assert back.kind == "resumed"

    record = back.record
    assert record.game.board == game.board and record.game.turn == BLACK
    assert record.game.variant is CAM
    assert record.seats == joiner.record.seats
    assert record.chat == [{"side": WHITE, "text": "hello"}]
    assert second.attach("j2", "abc", token=joiner.token).kind == "resumed"


def test_connections_are_not_remembered_across_a_restart(store, clock):
    first = Registry(store, clock=clock)
    creator, joiner = start_game(first)
    second = Registry(store, clock=clock)
    record = second.attach("c2", "abc", token=creator.token).record
    assert second.online(record, creator.token) and not second.online(record, joiner.token)


def test_an_unreadable_saved_game_is_ignored(store, registry):
    store.save("broken", "playing", 1.0, "this is not json")
    store.save("wrong", "playing", 1.0, json.dumps({"version": 99}))
    assert registry.attach("s1", "broken").kind == "waiting"
    assert registry.attach("s2", "wrong").kind == "waiting"


def test_chat_keeps_only_the_latest_messages():
    record = Record("abc", "camelot", "token", None, 0)
    for number in range(CHAT_LIMIT + 25):
        record.add_chat(WHITE, f"message {number}")
    assert len(record.chat) == CHAT_LIMIT
    assert record.chat[0]["text"] == "message 25" and record.chat[-1]["text"] == f"message {CHAT_LIMIT + 24}"


@pytest.mark.parametrize("damage", [
    lambda d: d.update(version=2),
    lambda d: d.pop("seats"),
    lambda d: d.update(seats={"white": "only-one-token"}),
    lambda d: d.update(chat=[{"nope": 1}]),
])
def test_records_reject_damaged_data(registry, damage):
    creator, joiner = start_game(registry)
    data = joiner.record.to_dict()
    damage(data)
    with pytest.raises(ValueError):
        Record.from_dict(data)


# --- expiry -----------------------------------------------------------------


@pytest.mark.parametrize("make_status, ttl_key", [
    ("waiting", "waiting"),
    ("playing", "playing"),
    ("finished", "finished"),
])
def test_games_expire_after_their_time_to_live(registry, store, clock, make_status, ttl_key):
    creator, joiner = start_game(registry) if make_status != "waiting" else (registry.attach("c", "abc"), None)
    if make_status == "finished":
        joiner.record.game.resign(WHITE)
        registry.save(joiner.record)
    registry.detach("creator-1" if joiner else "c")
    if joiner:
        registry.detach("joiner-1")

    clock.advance(DEFAULT_TTL[ttl_key] - 10)
    assert registry.purge_expired() == 0
    clock.advance(20)
    assert registry.purge_expired() == 1
    assert store.meta() == [] and registry.records() == []


def test_a_game_with_someone_connected_is_not_expired(registry, clock):
    creator, joiner = start_game(registry)
    registry.detach("joiner-1")
    clock.advance(DEFAULT_TTL["playing"] * 3)
    assert registry.purge_expired() == 0  # the creator is still connected

    registry.detach("creator-1")
    assert registry.purge_expired() == 1


def test_expired_games_can_no_longer_be_resumed(registry, clock):
    creator, joiner = start_game(registry)
    registry.detach("creator-1")
    registry.detach("joiner-1")
    clock.advance(DEFAULT_TTL["playing"] + 1)
    registry.purge_expired()
    with pytest.raises(Refused) as refusal:
        registry.attach("c2", "abc", token=creator.token, resume=True)
    assert refusal.value.code == "not-found"


def test_moves_keep_a_game_alive(registry, clock):
    creator, joiner = start_game(registry)
    registry.detach("creator-1")
    registry.detach("joiner-1")
    clock.advance(DEFAULT_TTL["playing"] - 60)
    registry.save(joiner.record)  # someone moved
    clock.advance(DEFAULT_TTL["playing"] - 60)
    assert registry.purge_expired() == 0


def test_the_time_to_live_can_be_changed(store, clock):
    registry = Registry(store, clock=clock, ttl={"waiting": 60})
    registry.attach("s1", "abc")
    registry.detach("s1")
    clock.advance(61)
    assert registry.purge_expired() == 1


def test_expired_games_are_swept_on_startup(store, clock):
    first = Registry(store, clock=clock)
    first.attach("s1", "abc")
    first.detach("s1")
    clock.advance(DEFAULT_TTL["waiting"] + 1)
    Registry(store, clock=clock)
    assert store.meta() == []


def test_connecting_sweeps_occasionally(registry, store, clock):
    registry.attach("s1", "old")
    registry.detach("s1")
    clock.advance(DEFAULT_TTL["waiting"] + PURGE_INTERVAL)
    registry.attach("s2", "new")
    assert [code for code, _, _ in store.meta()] == ["new"]


# --- stats ------------------------------------------------------------------


def test_stats_count_games_by_status_and_players_online(registry):
    assert registry.stats() == {"games": {"waiting": 0, "playing": 0, "finished": 0}, "playersOnline": 0}

    registry.attach("waiting-sid", "waiting")  # one player, one waiting game
    registry.attach("p1", "playing")
    registry.attach("p2", "playing")  # two players, a game in progress
    registry.attach("f1", "finished")
    done = registry.attach("f2", "finished")
    done.record.game.resign(WHITE)  # two players, a finished game
    registry.save(done.record)

    stats = registry.stats()
    assert stats["games"] == {"waiting": 1, "playing": 1, "finished": 1}
    assert stats["playersOnline"] == 5

    registry.detach("waiting-sid")
    assert registry.stats()["playersOnline"] == 4
