import json
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from pulse.history_store import HistoryStore


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'history.sqlite3'
        self.store = HistoryStore(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def sample(self, timestamp=None):
        return dict(timestamp=time.time() if timestamp is None else timestamp, cpu=90, memory=40,
                    battery=None, download=0, upload=0, disk_free=100, apps={'Editor': (50, 1000)})

    def test_defaults_and_database_details(self):
        result = self.store.settings()
        self.assertTrue(result['recordingEnabled'])
        self.assertEqual(result['database'], str(self.path.resolve()))
        self.assertGreater(result['databaseBytes'], 0)
        self.assertEqual(result['retention']['scanLimit'], 20)

    def test_pause_saves_pending_samples_and_persists_across_restarts(self):
        self.store.pending.put(self.sample())
        self.store.set_recording(False)
        self.assertFalse(self.store.recording_enabled)
        self.assertIsNotNone(self.store.settings()['lastSaved'])
        self.store.submit({})  # Paused submission must not inspect or queue process data.
        self.assertTrue(self.store.pending.empty())
        self.assertFalse(HistoryStore(self.path).recording_enabled)
        self.store.set_recording(True)
        self.assertTrue(HistoryStore(self.path).recording_enabled)

    def test_pause_boundary_cannot_bridge_busy_periods(self):
        start = time.time()-200
        self.store.write([self.sample(start+t) for t in range(0,64,2)])
        self.store.set_recording(False)
        self.store.set_recording(True)
        self.store.write([self.sample(start+t) for t in range(64,128,2)])
        events = self.store.performance_insights()['events']
        self.assertEqual(len(events), 2)
        self.assertNotEqual(events[0]['id'], events[1]['id'])

    def test_clearing_performance_keeps_scans_and_preferences(self):
        self.store.write([self.sample()])
        with self.store.connect() as db:
            db.execute('INSERT INTO scans(timestamp,payload) VALUES (?,?)', (time.time(), json.dumps({'path':'C:/Example'})))
        self.store.set_recording(False)
        self.store.pending.put(self.sample())
        self.store.clear_performance()
        self.store.flush()
        self.assertFalse(self.store.recording_enabled)
        self.assertIsNone(self.store.settings()['lastSaved'])
        self.assertEqual(self.store.settings()['scanCount'], 1)
        with self.store.connect() as db:
            for table in ('metrics','apps','metadata','insight_minutes','insight_events','insight_meta'):
                self.assertEqual(db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0], 0)

    def test_waiting_writer_cannot_resurrect_cleared_queue(self):
        self.store.pending.put(self.sample())
        with self.store.record_lock:
            writer = threading.Thread(target=self.store.flush)
            writer.start()
            self.store.clear_performance()
        writer.join(timeout=5)
        self.assertFalse(writer.is_alive())
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM metrics').fetchone()[0], 0)

    def test_failed_clear_preserves_pending_samples(self):
        self.store.pending.put(self.sample())
        with patch.object(self.store, 'connect', side_effect=sqlite3.OperationalError('busy')):
            with self.assertRaises(sqlite3.OperationalError):
                self.store.clear_performance()
        self.assertEqual(self.store.pending.qsize(), 1)

    def test_invalid_recording_preferences_are_rejected(self):
        for value in ('false', 0, None):
            with self.assertRaises(ValueError):
                self.store.set_recording(value)
