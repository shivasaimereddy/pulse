import json
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from pulse.database_workspace import DatabaseWorkspace, preferred_database, validate_database
from pulse.history_store import HistoryStore


class DatabaseWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = self.root / 'location.json'
        self.old = self.root / 'original.sqlite3'
        self.workspace = DatabaseWorkspace(self.old, self.config)
        self.workspace.start()

    def tearDown(self):
        self.workspace.close()
        self.tmp.cleanup()

    def sample(self):
        return dict(timestamp=time.time(), cpu=20, memory=30, battery=None,
                    download=0, upload=0, disk_free=100, apps={})

    def test_switch_flushes_old_history_keeps_it_and_uses_target_preferences(self):
        target = self.root / 'other.sqlite3'
        existing = HistoryStore(target)
        existing.set_recording(False)
        self.workspace._store.pending.put(self.sample())
        self.workspace.switch(target)
        self.assertEqual(self.workspace.path, target)
        self.assertFalse(self.workspace.recording_enabled)
        with sqlite3.connect(self.old) as db:
            self.assertGreater(db.execute('SELECT COUNT(*) FROM metrics').fetchone()[0], 0)
        with sqlite3.connect(target) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM metrics').fetchone()[0], 0)
        self.assertEqual(json.loads(self.config.read_text())['database'], str(target))
        with patch('pulse.database_workspace.preference_path', return_value=self.config):
            self.assertEqual(preferred_database(), target)

    def test_unrelated_and_invalid_files_remain_unchanged(self):
        for name, content in [('wrong.sqlite3', b'not sqlite'), ('wrong.txt', b'example')]:
            target = self.root / name
            target.write_bytes(content)
            with self.assertRaises((ValueError, sqlite3.Error)):
                self.workspace.switch(target)
            self.assertEqual(target.read_bytes(), content)
            self.assertEqual(self.workspace.path, self.old)
        target = self.root / 'unrelated.db'
        with sqlite3.connect(target) as db:
            db.execute('CREATE TABLE private_data(value TEXT)')
        before = target.read_bytes()
        with self.assertRaises(ValueError):
            self.workspace.switch(target)
        self.assertEqual(target.read_bytes(), before)

    def test_newer_database_is_rejected(self):
        target = self.root / 'future.sqlite3'
        with sqlite3.connect(target) as db:
            db.execute('PRAGMA user_version=999')
        with self.assertRaisesRegex(ValueError, 'newer'):
            validate_database(target)

    def test_config_failure_leaves_current_database_running(self):
        with patch('pulse.database_workspace.os.replace', side_effect=OSError('Read only')):
            with self.assertRaises(OSError):
                self.workspace.switch(self.root / 'new.sqlite3')
        self.assertEqual(self.workspace.path, self.old)
        self.assertTrue(self.workspace._store.worker.is_alive())

    def test_pending_save_error_prevents_switch(self):
        self.workspace.error = 'Disk full'
        with patch.object(self.workspace._store, 'flush'), self.assertRaisesRegex(ValueError, 'could not be saved'):
            self.workspace.switch(self.root / 'new.sqlite3')
        self.assertEqual(self.workspace.path, self.old)
        self.assertFalse(self.config.exists())

    def test_switch_waits_for_inflight_read(self):
        entered, release, switched = threading.Event(), threading.Event(), threading.Event()
        original = self.workspace._store.settings
        def read():
            entered.set()
            release.wait(3)
            return original()
        self.workspace._store.settings = read
        reader = threading.Thread(target=self.workspace.settings)
        reader.start()
        self.assertTrue(entered.wait(2))
        worker = threading.Thread(target=lambda: (self.workspace.switch(self.root / 'new.sqlite3'), switched.set()))
        worker.start()
        self.assertFalse(switched.wait(.1))
        release.set()
        reader.join(3)
        worker.join(3)
        self.assertTrue(switched.is_set())


if __name__ == '__main__':
    unittest.main()
