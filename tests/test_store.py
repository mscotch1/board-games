import pytest

from store import DATABASE_NAME, MemoryStore, SqliteStore, open_store


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    if request.param == "memory":
        yield MemoryStore()
    else:
        s = SqliteStore(str(tmp_path / "games.sqlite3"))
        yield s
        s.close()


def test_an_unknown_game_is_none(store):
    assert store.load("nope") is None


def test_a_saved_game_can_be_loaded(store):
    store.save("abc", "playing", 100.0, '{"hello": "world"}')
    assert store.load("abc") == '{"hello": "world"}'


def test_saving_again_replaces_the_game(store):
    store.save("abc", "waiting", 1.0, "first")
    store.save("abc", "playing", 2.0, "second")
    assert store.load("abc") == "second"
    assert store.meta() == [("abc", "playing", 2.0)]


def test_games_can_be_deleted(store):
    store.save("abc", "playing", 1.0, "x")
    store.save("def", "playing", 1.0, "y")
    store.delete("abc")
    store.delete("never-existed")
    assert store.load("abc") is None and store.load("def") == "y"


def test_meta_lists_every_game_without_its_data(store):
    store.save("a", "waiting", 1.0, "x")
    store.save("b", "finished", 2.5, "y")
    assert sorted(store.meta()) == [("a", "waiting", 1.0), ("b", "finished", 2.5)]


def test_text_with_any_characters_is_kept(store):
    text = '{"chat": "café ♕ \\"quoted\\" \\n"}'
    store.save("abc", "playing", 1.0, text)
    assert store.load("abc") == text


def test_sqlite_keeps_games_across_a_restart(tmp_path):
    path = str(tmp_path / "games.sqlite3")
    first = SqliteStore(path)
    first.save("abc", "playing", 5.0, "kept")
    first.close()

    second = SqliteStore(path)
    assert second.load("abc") == "kept"
    assert second.meta() == [("abc", "playing", 5.0)]
    second.close()


def test_sqlite_creates_its_directory(tmp_path):
    nested = tmp_path / "a" / "b" / "games.sqlite3"
    SqliteStore(str(nested)).close()
    assert nested.exists()


def test_open_store_picks_the_kind_from_the_setting(tmp_path):
    for nothing in (None, "", ":memory:", "memory"):
        assert isinstance(open_store(nothing), MemoryStore)

    store = open_store(str(tmp_path / "data"))
    assert isinstance(store, SqliteStore)
    store.close()
    assert (tmp_path / "data" / DATABASE_NAME).exists()
