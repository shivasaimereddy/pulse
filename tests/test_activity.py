import json
import tempfile
import unittest
from pathlib import Path

from pulse.activity_timeline import recording_gaps
from pulse.history_store import HistoryStore


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = HistoryStore(Path(self.tmp.name) / 'history.sqlite3')
        self.now = 1800000000

    def tearDown(self):
        self.tmp.cleanup()

    def save_comparison(self, timestamp, net=10, available=True, count=1):
        comparison = dict(available=available, previousAt=timestamp-86400, currentAt=timestamp,
                          net=net, added=max(0, net), reduced=max(0, -net), count=count,
                          fileCount=count, items=[], files=[])
        with self.store.connect() as db:
            return db.execute('INSERT INTO scans(timestamp,payload) VALUES (?,?)',
                              (timestamp, json.dumps(dict(path='C:/Example', changes=comparison)))).lastrowid

    def test_empty_database_does_not_invent_a_gap(self):
        result = self.store.activity_timeline(now=self.now)
        self.assertEqual(result['events'], [])
        self.assertIsNone(result['since'])

    def test_missing_minutes_are_bounded_and_only_after_recording_began(self):
        self.assertEqual(recording_gaps([], 0, 1000, None), [])
        self.assertEqual(recording_gaps([0, 60, 240], 0, 300, 0),
                         [dict(id='gap:120:240', kind='gap', start=120, end=240)])
        self.assertEqual(recording_gaps([600, 660], 0, 720, 605), [])
        self.assertEqual(recording_gaps([0], 0, 179, 0), [])

    def test_historical_comparisons_keep_exact_identity_and_interval(self):
        first = self.save_comparison(self.now-100, 10)
        second = self.save_comparison(self.now-50, 20)
        result = self.store.activity_timeline(now=self.now)
        self.assertEqual([event['scanId'] for event in result['events']], [second, first])
        self.assertLess(result['events'][0]['start'], result['start'])
        self.assertEqual(self.store.activity_comparison(first)['comparison']['net'], 10)
        self.assertEqual(self.store.activity_comparison(second)['comparison']['net'], 20)
        self.assertIsNone(self.store.activity_comparison(999))

    def test_incomplete_unchanged_old_and_future_comparisons_are_excluded(self):
        self.save_comparison(self.now-100, available=False)
        self.save_comparison(self.now-90, net=0, count=0)
        self.save_comparison(self.now-100000)
        self.save_comparison(self.now+10)
        self.assertEqual(self.store.activity_timeline(now=self.now)['events'], [])
        ident = self.save_comparison(self.now-10, net=0, count=2)
        self.assertEqual(self.store.activity_timeline(now=self.now)['events'][0]['scanId'], ident)

    def test_busy_periods_and_app_evidence_share_the_timeline(self):
        self.store.write([dict(timestamp=self.now-100+t, cpu=90, memory=40,
                               battery=None, download=0, upload=0, disk_free=100,
                               apps={'Editor': (50, 1000)}) for t in range(0, 64, 2)], now=self.now)
        result = self.store.activity_timeline(now=self.now)
        event = next(event for event in result['events'] if event['kind'] == 'performance')
        self.assertEqual(event['observation']['average'], 90)
        self.assertEqual(event['observation']['apps'][0]['name'], 'Editor')
        self.assertEqual(event['observation']['status'], 'interrupted')

    def test_erased_scan_cannot_be_opened_from_old_timeline(self):
        ident = self.save_comparison(self.now-10)
        self.store.clear_scans()
        self.assertIsNone(self.store.activity_comparison(ident))
        self.assertFalse(any(event['kind'] == 'storage' for event in self.store.activity_timeline(now=self.now)['events']))

    def test_invalid_range_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store.activity_timeline('30d', now=self.now)

    def test_large_gap_history_is_bounded_and_counts_match_loaded_events(self):
        beginning = self.now - 600 * 180
        with self.store.connect() as db:
            db.execute("INSERT INTO insight_meta VALUES ('since',?)", (beginning,))
            db.executemany('INSERT INTO insight_minutes VALUES (?,?,?,?,?,?,?)',
                           [(beginning+i*180, 1, 1, 1, 1, 1, '{}') for i in range(601)])
        result = self.store.activity_timeline('7d', now=self.now)
        self.assertEqual(len(result['events']), 300)
        self.assertTrue(result['truncated'])
        self.assertEqual(result['summary']['gap'], 300)
        self.assertEqual(result['events'], sorted(result['events'], key=lambda event: (-event['end'], event['id'])))
