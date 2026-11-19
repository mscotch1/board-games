import os
import shutil
import sqlite3
import time
import types

import pytest

import app as app_module
from backups import (
    BackupScheduler,
    backup_name,
    backup_time,
    latest_backup_time,
    list_backups,
    make_backup,
    start_backups,
)
from registry import Registry
from rules import BLACK, WHITE
from store import MemoryStore, SqliteStore

NOON = 1_800_000_000  # a fixed moment: 2027-01-15 08:00:00 UTC


class Clock:
    def __init__(self, now=NOON):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def store(tmp_path):
    s = SqliteStore(str(tmp_path / "data" / "games.sqlite3"))
    s.save("abc", "playing", 1.0, '{"hello": "world"}')
    s.save("def", "waiting", 2.0, "second game")
    yield s
    s.close()


# --- names ------------------------------------------------------------------


def test_backups_are_named_by_when_they_were_made():
    assert backup_name(NOON) == "games-20270115-080000.sqlite3"
    assert backup_name(0) == "games-19700101-000000.sqlite3"


def test_a_name_gives_back_the_time():
    for moment in (0, NOON, NOON + 12345):
        assert backup_time(backup_name(moment)) == moment


@pytest.mark.parametrize("name", ["games.sqlite3", "games-2027.sqlite3", "notes.txt", "games-20270115-080000.sqlite3.partial", "../games-20270115-080000.sqlite3"])
def test_other_names_are_not_backups(name):
    assert backup_time(name) is None


# --- taking a backup --------------------------------------------------------


def test_a_backup_is_a_complete_copy(store, tmp_path):
    destination = str(tmp_path / "copy.sqlite3")
    store.backup(destination)

    copy = SqliteStore(destination)
    assert copy.load("abc") == '{"hello": "world"}' and copy.load("def") == "second game"
    assert sorted(copy.meta()) == sorted(store.meta())
    copy.close()


def test_a_backup_leaves_no_half_written_file_and_changes_nothing(store, tmp_path):
    store.backup(str(tmp_path / "copy.sqlite3"))
    assert sorted(os.listdir(tmp_path)) == ["copy.sqlite3", "data"]
    assert store.load("abc") == '{"hello": "world"}'


def test_the_store_keeps_working_after_a_backup(store, tmp_path):
    store.backup(str(tmp_path / "copy.sqlite3"))
    store.save("abc", "finished", 3.0, "changed")
    assert store.load("abc") == "changed"
    copy = SqliteStore(str(tmp_path / "copy.sqlite3"))
    assert copy.load("abc") == '{"hello": "world"}'  # the backup is a snapshot
    copy.close()


def test_a_backup_overwrites_nothing_it_should_not(store, tmp_path):
    destination = str(tmp_path / "copy.sqlite3")
    store.backup(destination)
    store.save("ghi", "playing", 4.0, "third")
    store.backup(destination)  # same name again: replaced by the newer copy
    copy = SqliteStore(destination)
    assert copy.load("ghi") == "third"
    copy.close()


# --- keeping the newest few -------------------------------------------------


def test_listing_backups_finds_only_backups_oldest_first(tmp_path):
    for name in ["games-20270116-000000.sqlite3", "games-20270115-000000.sqlite3", "games.sqlite3", "readme.txt"]:
        (tmp_path / name).write_text("x")
    assert list_backups(str(tmp_path)) == ["games-20270115-000000.sqlite3", "games-20270116-000000.sqlite3"]
    assert list_backups(str(tmp_path / "nowhere")) == []


def test_making_a_backup_creates_the_directory(store, tmp_path):
    directory = str(tmp_path / "a" / "b" / "backups")
    path = make_backup(store, directory, keep=3, moment=NOON)
    assert path == os.path.join(directory, "games-20270115-080000.sqlite3") and os.path.exists(path)


def test_only_the_newest_backups_are_kept(store, tmp_path):
    directory = str(tmp_path / "backups")
    for day in range(6):
        make_backup(store, directory, keep=3, moment=NOON + day * 86400)
    kept = list_backups(directory)
    assert len(kept) == 3
    assert [backup_time(n) for n in kept] == [NOON + d * 86400 for d in (3, 4, 5)]


def test_a_keep_of_zero_keeps_everything(store, tmp_path):
    directory = str(tmp_path / "backups")
    for day in range(4):
        make_backup(store, directory, keep=0, moment=NOON + day * 86400)
    assert len(list_backups(directory)) == 4


def test_only_backups_are_ever_deleted(store, tmp_path):
    directory = tmp_path / "backups"
    directory.mkdir()
    (directory / "important-notes.txt").write_text("mine")
    for day in range(4):
        make_backup(store, str(directory), keep=1, moment=NOON + day * 86400)
    assert (directory / "important-notes.txt").read_text() == "mine"


# --- the schedule -----------------------------------------------------------


def test_a_backup_is_made_when_there_is_none(store, tmp_path):
    scheduler = BackupScheduler(store, str(tmp_path / "b"), 3600, 7, clock=Clock())
    assert scheduler.last_backup_at is None
    assert scheduler.run_once() is not None
    assert scheduler.last_backup_at == NOON


def test_another_is_made_only_when_the_interval_has_passed(store, tmp_path):
    clock = Clock()
    scheduler = BackupScheduler(store, str(tmp_path / "b"), 3600, 7, clock=clock)
    scheduler.run_once()

    clock.advance(3599)
    assert scheduler.run_once() is None
    clock.advance(1)
    assert scheduler.run_once() is not None
    assert len(list_backups(scheduler.directory)) == 2


def test_a_server_that_was_down_catches_up(store, tmp_path):
    directory = str(tmp_path / "b")
    make_backup(store, directory, keep=7, moment=NOON - 10 * 86400)
    scheduler = BackupScheduler(store, directory, 86400, 7, clock=Clock())
    assert scheduler.run_once() is not None  # the newest is ten days old


def test_a_restart_does_not_make_a_backup_every_time(store, tmp_path):
    directory = str(tmp_path / "b")
    make_backup(store, directory, keep=7, moment=NOON - 60)
    assert BackupScheduler(store, directory, 86400, 7, clock=Clock()).run_once() is None


def test_the_background_thread_makes_backups_and_stops(store, tmp_path):
    scheduler = BackupScheduler(store, str(tmp_path / "b"), 3600, 7, check_every=0.05).start()
    deadline = time.time() + 5
    while not list_backups(scheduler.directory) and time.time() < deadline:
        time.sleep(0.02)
    scheduler.stop()
    assert len(list_backups(scheduler.directory)) == 1
    assert not scheduler._thread.is_alive()


def test_a_failed_backup_is_retried_and_does_not_kill_the_thread(store, tmp_path, caplog):
    real = store.backup
    attempts = []

    def flaky(destination):
        attempts.append(destination)
        if len(attempts) == 1:
            raise OSError("disk full")
        real(destination)

    store.backup = flaky
    scheduler = BackupScheduler(store, str(tmp_path / "b"), 3600, 7, check_every=0.05).start()
    deadline = time.time() + 5
    while not list_backups(scheduler.directory) and time.time() < deadline:
        time.sleep(0.02)
    scheduler.stop()
    assert len(attempts) >= 2 and len(list_backups(scheduler.directory)) == 1
    assert "backup failed" in caplog.text


# --- starting them ----------------------------------------------------------


def test_nothing_starts_for_a_store_that_cannot_be_backed_up(tmp_path):
    assert start_backups(MemoryStore(), str(tmp_path), interval_hours=24, keep=7) is None


def test_a_zero_interval_turns_backups_off(store, tmp_path):
    assert start_backups(store, str(tmp_path / "b"), interval_hours=0, keep=7) is None
    assert list_backups(str(tmp_path / "b")) == []


def test_starting_backups_makes_the_first_one(store, tmp_path):
    scheduler = start_backups(store, str(tmp_path / "b"), interval_hours=24, keep=7)
    deadline = time.time() + 5
    while not list_backups(scheduler.directory) and time.time() < deadline:
        time.sleep(0.02)
    scheduler.stop()
    assert len(list_backups(scheduler.directory)) == 1


# --- getting a game back from a backup --------------------------------------


def test_restoring_a_backup_brings_the_games_back(tmp_path):
    live = str(tmp_path / "live" / "games.sqlite3")
    original = Registry(SqliteStore(live))
    creator = original.attach("c", "abc", side=WHITE)
    joiner = original.attach("j", "abc")
    game = joiner.record.game
    game.play_turn(WHITE, list(game.legal_turns[0].moves))
    joiner.record.add_chat(WHITE, "before the disaster")
    original.save(joiner.record)

    backup = make_backup(original._store, str(tmp_path / "backups"), keep=7, moment=NOON)
    original._store.close()
    os.remove(live)  # the data volume is lost

    # restoring is copying the backup into place
    restored_dir = tmp_path / "restored"
    restored_dir.mkdir()
    shutil.copy(backup, restored_dir / "games.sqlite3")
    after = Registry(SqliteStore(str(restored_dir / "games.sqlite3")))

    back = after.attach("c2", "abc", token=creator.token)
    assert back.kind == "resumed"
    assert back.record.game.board == game.board and back.record.game.turn == BLACK
    assert back.record.chat == [{"side": WHITE, "text": "before the disaster"}]
    assert after.attach("j2", "abc", token=joiner.token).kind == "resumed"


def test_a_backup_is_an_ordinary_sqlite_file(store, tmp_path):
    path = make_backup(store, str(tmp_path / "b"), keep=7, moment=NOON)
    rows = sqlite3.connect(path).execute("SELECT code, status FROM games ORDER BY code").fetchall()
    assert rows == [("abc", "playing"), ("def", "waiting")]


# --- reported by the health check -------------------------------------------


def test_healthz_reports_the_last_backup(monkeypatch):
    monkeypatch.setattr(app_module, "registry", Registry(MemoryStore()))
    client = app_module.app.test_client()
    assert "lastBackup" not in client.get("/healthz").get_json()  # backups are off in tests

    monkeypatch.setattr(app_module, "backup_scheduler", types.SimpleNamespace(last_backup_at=NOON))
    assert client.get("/healthz").get_json()["lastBackup"] == "2027-01-15T08:00:00+00:00"

    monkeypatch.setattr(app_module, "backup_scheduler", types.SimpleNamespace(last_backup_at=None))
    assert client.get("/healthz").get_json()["lastBackup"] is None
