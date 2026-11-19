"""Limits and headers that keep a public server safe."""

import os

import pytest
from socketio.exceptions import ConnectionRefusedError as SocketIORefusal

import app as app_module
from ratelimit import RateLimiter
from registry import Refused, Registry
from rules import WHITE
from store import MemoryStore, SqliteStore


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


# --- the limiter ------------------------------------------------------------


def test_a_burst_is_allowed_and_then_it_runs_dry():
    limiter = RateLimiter(1, 3, clock=Clock())
    assert [limiter.allow("a") for _ in range(5)] == [True, True, True, False, False]


def test_tokens_come_back_over_time():
    clock = Clock()
    limiter = RateLimiter(2, 4, clock=clock)  # two a second, up to four saved
    for _ in range(4):
        limiter.allow("a")
    assert not limiter.allow("a")

    clock.advance(1)  # two back
    assert limiter.allow("a") and limiter.allow("a") and not limiter.allow("a")

    clock.advance(100)  # never more than the burst
    assert [limiter.allow("a") for _ in range(5)] == [True] * 4 + [False]


def test_each_key_has_its_own_bucket():
    limiter = RateLimiter(1, 1, clock=Clock())
    assert limiter.allow("a") and not limiter.allow("a")
    assert limiter.allow("b")


def test_a_refused_request_costs_nothing():
    clock = Clock()
    limiter = RateLimiter(1, 2, clock=clock)
    limiter.allow("a", cost=2)
    for _ in range(10):
        assert not limiter.allow("a")  # these must not push the balance further down
    clock.advance(1)
    assert limiter.allow("a")


def test_expensive_requests_need_enough_tokens():
    limiter = RateLimiter(1, 5, clock=Clock())
    assert limiter.allow("a", cost=5)
    assert not limiter.allow("a", cost=5)


def test_forgetting_a_key_starts_it_fresh():
    limiter = RateLimiter(0.001, 1, clock=Clock())
    limiter.allow("a")
    assert not limiter.allow("a")
    limiter.forget("a")
    assert limiter.allow("a")
    limiter.forget("never-seen")


def test_memory_stays_bounded_under_a_flood_of_keys():
    clock = Clock()
    limiter = RateLimiter(1, 10, clock=clock, max_keys=100)
    for number in range(5000):
        clock.advance(0.001)
        limiter.allow(f"client-{number}")
    assert len(limiter._buckets) <= 100


def test_idle_buckets_are_dropped_first():
    clock = Clock()
    limiter = RateLimiter(1, 2, clock=clock, max_keys=3)
    for key in "abc":
        limiter.allow(key)
    clock.advance(10)  # all three have refilled completely
    limiter.allow("d")
    assert set(limiter._buckets) == {"d"}


# --- the registry's guards --------------------------------------------------


def test_the_registry_stops_making_games_at_its_cap():
    registry = Registry(MemoryStore(), max_games=2)
    registry.attach("s1", "one")
    registry.attach("s2", "two")
    with pytest.raises(Refused) as refusal:
        registry.attach("s3", "three")
    assert refusal.value.code == "busy"

    # people can still join and return to games that exist
    assert registry.attach("s4", "one").kind == "started"
    assert registry.attach("s5", "two", token=registry.records()[1].creator_token).kind == "waiting"


def test_a_finished_games_slot_is_freed_when_it_expires():
    clock = Clock()
    clock.now = 1000.0
    registry = Registry(MemoryStore(), max_games=1, clock=clock)
    registry.attach("s1", "one")
    registry.detach("s1")
    clock.advance(24 * 3600 + 1)
    registry.purge_expired()
    assert registry.attach("s2", "two").kind == "waiting"


def test_before_create_runs_only_for_new_games():
    calls = []
    registry = Registry(MemoryStore())
    creator = registry.attach("s1", "abc", before_create=lambda: calls.append("made"))
    registry.attach("s2", "abc", before_create=lambda: calls.append("joined"))
    registry.attach("s3", "abc", token=creator.token, before_create=lambda: calls.append("returned"))
    assert calls == ["made"]


def test_before_create_can_stop_a_game_being_made():
    def deny():
        raise Refused("no", "rate-limited")

    registry = Registry(MemoryStore())
    with pytest.raises(Refused):
        registry.attach("s1", "abc", before_create=deny)
    assert registry.records() == [] and registry.stats()["games"]["waiting"] == 0


# --- the limits as the app applies them -------------------------------------


@pytest.fixture(autouse=True)
def fresh_registry(monkeypatch):
    monkeypatch.setattr(app_module, "registry", Registry(MemoryStore()))


def connect(code, headers=None, **auth):
    return app_module.socketio.test_client(app_module.app, auth={"code": code, **auth}, headers=headers)


def messages(client):
    out = []
    for m in client.get_received():
        if m["name"] == "message":
            args = m["args"]
            data = args[0] if isinstance(args, list) else args
            out.append((data["topic"], data["message"]))
    return out


def test_one_address_cannot_start_games_without_limit(monkeypatch):
    monkeypatch.setattr(app_module, "new_game_limiter", RateLimiter(0.0001, 2))
    assert connect("a").is_connected() and connect("b").is_connected()
    assert not connect("c").is_connected()


def test_the_refusal_says_why(monkeypatch):
    monkeypatch.setattr(app_module, "new_game_limiter", RateLimiter(0.0001, 1))
    connect("a")
    with app_module.app.test_request_context():
        app_module.request.sid = "someone"
        with pytest.raises(SocketIORefusal) as raised:
            app_module.handle_connect({"code": "b"})
    assert raised.value.error_args["data"] == {"code": "rate-limited"}


def test_joining_and_returning_are_not_limited(monkeypatch):
    monkeypatch.setattr(app_module, "new_game_limiter", RateLimiter(0.0001, 1))
    connect("a", token="a" * 22)  # uses up the one game
    assert connect("a").is_connected()  # joining it is fine
    assert connect("a", token="a" * 22, resume=True).is_connected()  # and so is coming back


def test_different_addresses_are_counted_separately(monkeypatch):
    monkeypatch.setattr(app_module, "new_game_limiter", RateLimiter(0.0001, 1))
    monkeypatch.setattr(app_module, "CLIENT_IP_HEADER", "CF-Connecting-IP")
    assert connect("a", headers={"CF-Connecting-IP": "203.0.113.1"}).is_connected()
    assert not connect("b", headers={"CF-Connecting-IP": "203.0.113.1"}).is_connected()
    assert connect("c", headers={"CF-Connecting-IP": "203.0.113.2"}).is_connected()


def test_the_client_address_comes_from_the_trusted_header_only(monkeypatch):
    with app_module.app.test_request_context(headers={"CF-Connecting-IP": "203.0.113.9, 10.0.0.1"}, environ_base={"REMOTE_ADDR": "10.1.1.1"}):
        monkeypatch.setattr(app_module, "CLIENT_IP_HEADER", None)
        assert app_module.client_address() == "10.1.1.1"  # not trusted: the header could be anything
        monkeypatch.setattr(app_module, "CLIENT_IP_HEADER", "CF-Connecting-IP")
        assert app_module.client_address() == "203.0.113.9"
    with app_module.app.test_request_context(environ_base={"REMOTE_ADDR": "10.1.1.1"}):
        assert app_module.client_address() == "10.1.1.1"  # trusted header missing: fall back


def test_a_full_server_turns_new_games_away():
    app_module.registry = Registry(MemoryStore(), max_games=1)
    assert connect("a").is_connected()
    assert not connect("b").is_connected()
    assert connect("a").is_connected()  # but the game that exists can still be joined


def test_a_flood_of_messages_is_ignored_beyond_the_limit(monkeypatch):
    monkeypatch.setattr(app_module, "message_limiter", RateLimiter(0.0001, 3))
    a, b = connect("abc", side=WHITE), connect("abc")
    a.get_received(), b.get_received()
    for number in range(10):
        a.emit("message", {"topic": "chat", "message": {"text": f"spam {number}"}})
    assert [m["text"] for _, m in messages(b)] == ["spam 0", "spam 1", "spam 2"]


def test_each_connection_has_its_own_message_allowance(monkeypatch):
    monkeypatch.setattr(app_module, "message_limiter", RateLimiter(0.0001, 1))
    a, b = connect("abc", side=WHITE), connect("abc")
    a.get_received(), b.get_received()
    a.emit("message", {"topic": "chat", "message": {"text": "from a"}})
    b.emit("message", {"topic": "chat", "message": {"text": "from b"}})
    assert [m["text"] for _, m in messages(b)] == ["from a"]
    assert [m["text"] for _, m in messages(a)] == ["from b"]


# --- headers ----------------------------------------------------------------


@pytest.fixture
def static_dir(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("landing")
    monkeypatch.setitem(app_module.app.config, "STATIC_DIR", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize("url", ["/", "/healthz", "/version", "/missing-page"])
def test_every_response_carries_the_security_headers(static_dir, url):
    response = app_module.app.test_client().get(url)
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["Permissions-Policy"]
    assert "Content-Security-Policy" in response.headers


def test_the_policy_allows_only_this_site():
    policy = app_module.content_security_policy("games.example.com")
    directives = dict(part.split(" ", 1) for part in policy.split("; "))
    assert directives["default-src"] == "'self'"
    assert directives["script-src"] == "'self'"  # in particular, no 'unsafe-inline'
    assert directives["style-src"] == "'self'"
    assert directives["img-src"] == "'self' data:"
    assert directives["object-src"] == "'none'"
    assert directives["frame-ancestors"] == "'none'"
    assert directives["connect-src"] == "'self' ws://games.example.com wss://games.example.com"
    assert "unsafe" not in policy and "*" not in policy


@pytest.mark.parametrize("host", ["evil.com; script-src *", "a b", "x.com\nSet-Cookie: a=b", "", None, "h:123456"])
def test_an_odd_host_header_cannot_change_the_policy(host):
    policy = app_module.content_security_policy(host)
    assert policy.count(";") == 9  # still ten directives, nothing added
    assert "connect-src 'self'" in policy and "ws://" not in policy


def test_the_policy_names_the_host_the_request_was_for(static_dir):
    response = app_module.app.test_client().get("/", headers={"Host": "play.example.org:8443"})
    assert "ws://play.example.org:8443 wss://play.example.org:8443" in response.headers["Content-Security-Policy"]


def test_strict_transport_security_is_opt_in(static_dir, monkeypatch):
    assert "Strict-Transport-Security" not in app_module.app.test_client().get("/").headers
    monkeypatch.setattr(app_module, "HSTS_MAX_AGE", 31536000)
    assert app_module.app.test_client().get("/").headers["Strict-Transport-Security"] == "max-age=31536000"


# --- an unusable data directory ---------------------------------------------


def test_an_unwritable_data_directory_is_explained(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "access", lambda *args, **kwargs: False)
    with pytest.raises(PermissionError, match="isn't writable.*uid 10001"):
        SqliteStore(str(tmp_path / "data" / "games.sqlite3"))
