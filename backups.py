"""Regular backups of the saved games.

A backup is a complete, consistent copy of the SQLite file, taken while the server is
running (SQLite's own backup API, not a file copy that could catch a write half done).
They are named by when they were made, and only the newest few are kept. To restore one,
stop the server and copy it over `games.sqlite3` in the data directory (see the README).
"""

import logging
import os
import re
import threading
import time
from datetime import datetime, timezone

log = logging.getLogger(__name__)

BACKUP_NAME = re.compile(r"games-(\d{8})-(\d{6})\.sqlite3")


def backup_name(moment):
    """The file name for a backup made at `moment` (seconds since the epoch), in UTC."""
    return datetime.fromtimestamp(moment, timezone.utc).strftime("games-%Y%m%d-%H%M%S.sqlite3")


def backup_time(name):
    """When the backup called `name` was made, or None if it isn't a backup's name."""
    match = BACKUP_NAME.fullmatch(name)
    if not match:
        return None
    stamp = datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")
    return stamp.replace(tzinfo=timezone.utc).timestamp()


def list_backups(directory):
    """The backups in `directory`, oldest first."""
    try:
        names = os.listdir(directory)
    except FileNotFoundError:
        return []
    return sorted(name for name in names if BACKUP_NAME.fullmatch(name))


def make_backup(store, directory, keep, moment):
    """Back `store` up into `directory`, then delete all but the newest `keep` backups.
    Returns the new backup's path."""
    os.makedirs(directory, exist_ok=True)
    destination = os.path.join(directory, backup_name(moment))
    store.backup(destination)

    for name in list_backups(directory)[:-keep] if keep > 0 else []:
        os.remove(os.path.join(directory, name))
    return destination


def latest_backup_time(directory):
    """When the newest backup in `directory` was made, or None if there isn't one."""
    backups = list_backups(directory)
    return backup_time(backups[-1]) if backups else None


class BackupScheduler:
    """Makes a backup whenever the newest one is older than `interval` seconds.

    It looks every `check_every` seconds in a background thread, so a server that restarts
    often still backs up once a day, and one that was down for a while catches up when it
    comes back. A failed backup is logged and tried again at the next check.
    """

    def __init__(self, store, directory, interval, keep, *, clock=time.time, check_every=600):
        self._store = store
        self.directory = directory
        self._interval = interval
        self._keep = keep
        self._clock = clock
        self._check_every = check_every
        self._stop = threading.Event()
        self._thread = None

    @property
    def last_backup_at(self):
        return latest_backup_time(self.directory)

    def run_once(self):
        """Back up now if one is due. Returns the new backup's path, or None."""
        now = self._clock()
        latest = latest_backup_time(self.directory)
        if latest is not None and now - latest < self._interval:
            return None
        path = make_backup(self._store, self.directory, self._keep, now)
        log.info("backed up the saved games to %s", path)
        return path

    def start(self):
        self._thread = threading.Thread(target=self._loop, name="backups", daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception:
                log.exception("backup failed; will try again")
            self._stop.wait(self._check_every)


def start_backups(store, directory, interval_hours, keep):
    """Start regular backups of `store`, if it can be backed up (a SQLite file) and they aren't
    turned off (`interval_hours` of 0). Returns the scheduler, or None."""
    if interval_hours <= 0 or not hasattr(store, "backup"):
        return None
    return BackupScheduler(store, directory, interval_hours * 3600, keep).start()
