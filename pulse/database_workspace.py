"""Switch local databases without letting an in-flight operation cross workspaces."""
import json
import os
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

from .history_store import HistoryStore
from .launch_options import appdata_database


def preference_path():
    return appdata_database().parent / 'database-location.json'


def preferred_database():
    try:
        path = Path(json.loads(preference_path().read_text(encoding='utf-8'))['database'])
        return path if path.is_absolute() else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def validate_database(path):
    path = Path(path).expanduser()
    if not path.is_absolute() or str(path).startswith(('\\\\', '//')):
        raise ValueError('Choose a database on a local drive.')
    path = path.resolve()
    if path.suffix.lower() not in ('.sqlite3', '.sqlite', '.db'):
        raise ValueError('Choose a Pulse database (.sqlite3, .sqlite or .db).')
    if path.exists():
        # Inspect existing files read-only before HistoryStore can run migrations.
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
            if db.execute('PRAGMA user_version').fetchone()[0] > 3:
                raise ValueError('This database needs a newer version of Pulse.')
            expected = {'metrics': {'resolution', 'bucket', 'n', 'cpu', 'cpu_peak', 'memory', 'memory_peak',
                                    'download', 'upload', 'disk_free', 'battery', 'battery_n'},
                        'apps': {'bucket', 'name', 'cpu', 'memory', 'n', 'peak'},
                        'scans': {'id', 'timestamp', 'payload'}}
            for table, columns in expected.items():
                actual = {row[1] for row in db.execute('PRAGMA table_info(' + table + ')')}
                if not columns <= actual:
                    raise ValueError('This file is not a compatible Pulse database. Your current database has not changed.')
            if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('This database needs repair. Your current database has not changed.')
    return path


class DatabaseWorkspace:
    """Keep a stable service reference; serialize calls while the backing store changes."""
    def __init__(self, path, config=None):
        self._gate = threading.RLock()
        self._store = HistoryStore(path)
        self._config = Path(config) if config else preference_path()

    def __getattr__(self, name):
        with self._gate:
            value = getattr(self._store, name)
        if not callable(value):
            return value
        def call(*args, **kwargs):
            with self._gate:
                return getattr(self._store, name)(*args, **kwargs)
        return call

    @property
    def error(self):
        with self._gate:
            return self._store.error

    @error.setter
    def error(self, value):
        with self._gate:
            self._store.error = value

    def switch(self, path):
        with self._gate:
            path = validate_database(path)
            if path == self._store.path.resolve():
                return self._store.latest_scan()
            self._store.flush()
            if self._store.error:
                raise ValueError('Current history could not be saved. Resolve the recording error before changing databases.')
            candidate = HistoryStore(path)
            try:
                saved = candidate.latest_scan()
                candidate.start()
                self._config.parent.mkdir(parents=True, exist_ok=True)
                temporary = self._config.with_suffix('.tmp')
                temporary.write_text(json.dumps({'database': str(path)}), encoding='utf-8')
                os.replace(temporary, self._config)
            except Exception:
                candidate.close()
                raise
            self._store.close()
            self._store = candidate
            return saved
