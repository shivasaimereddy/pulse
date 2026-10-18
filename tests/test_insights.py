import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pulse.history_store import HistoryStore
from pulse.performance_insights import InsightEngine,compact_apps,DAY


class InsightTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'history.sqlite3'
        self.store=HistoryStore(self.path)
        self.now=1800000000

    def tearDown(self):
        self.tmp.cleanup()

    def sample(self,offset,cpu=90,memory=50):
        return dict(timestamp=self.now+offset,cpu=cpu,memory=memory,battery=None,
                    download=0,upload=0,disk_free=100,apps={'Browser':(60,1000)})

    def test_short_spike_does_not_create_event(self):
        self.store.write([self.sample(t) for t in range(0,60,2)]+[self.sample(60,cpu=10)],now=self.now+60)
        self.assertEqual(self.store.performance_insights(now=self.now+60)['events'],[])

    def test_sustained_event_records_apps_and_finishes_at_last_high_sample(self):
        self.store.write([self.sample(t) for t in range(0,64,2)],now=self.now+64)
        result=self.store.performance_insights(now=self.now+64)
        self.assertEqual(result['summary']['events'],1)
        event=result['events'][0]
        self.assertEqual(event['status'],'active')
        self.assertEqual(event['average'],90)
        self.assertEqual(event['apps'][0]['cpu'],60)
        self.store.write([self.sample(64,cpu=10)],now=self.now+64)
        self.assertEqual(self.store.performance_insights(now=self.now+64)['events'][0]['status'],'ended')
        self.assertEqual(self.store.performance_insights(now=self.now+64)['summary']['cpuSeconds'],62)

    def test_recording_gap_and_restart_do_not_bridge_events(self):
        self.store.write([self.sample(t) for t in range(0,64,2)],now=self.now+64)
        self.store.write([self.sample(200)],now=self.now+200)
        result=self.store.performance_insights(now=self.now+200)
        self.assertEqual(len(result['events']),1)
        self.assertEqual(result['events'][0]['status'],'interrupted')
        self.assertEqual(result['events'][0]['end'],self.now+62)
        reopened=HistoryStore(self.path)
        reopened.write([self.sample(t) for t in range(202,266,2)],now=self.now+266)
        result=reopened.performance_insights(now=self.now+266)
        self.assertEqual(len(result['events']),2)
        self.assertEqual(result['events'][0]['start'],self.now+202)

    def test_overlap_is_not_counted_as_repeated_periods(self):
        self.store.write([self.sample(t,memory=90) for t in range(0,64,2)],now=self.now+64)
        result=self.store.performance_insights(now=self.now+64)
        self.assertEqual(len(result['events']),2)
        self.assertEqual(result['repeated'],[])
        self.store.write([self.sample(64,cpu=0,memory=20)]+[self.sample(t) for t in range(66,130,2)],now=self.now+130)
        self.assertEqual(self.store.performance_insights(now=self.now+130)['repeated'][0]['events'],2)

    def test_sparse_samples_do_not_claim_sustained_pressure(self):
        self.store.write([self.sample(t) for t in range(0,181,10)],now=self.now+180)
        self.assertEqual(self.store.performance_insights(now=self.now+180)['events'],[])

    def test_failed_batch_does_not_advance_detector(self):
        samples=[self.sample(t) for t in range(0,64,2)]
        from pulse import performance_insights
        real=performance_insights.write
        def fail(db,samples,engine,session,now):
            real(db,samples,engine,session,now)
            raise sqlite3.OperationalError('busy')
        with patch('pulse.performance_insights.write',side_effect=fail):
            with self.assertRaises(sqlite3.OperationalError):self.store.write(samples,now=self.now+64)
        self.assertIsNone(self.store.insight_engine.last)
        self.store.write(samples,now=self.now+64)
        result=self.store.performance_insights(now=self.now+64)
        self.assertEqual(len(result['events']),1)
        self.assertEqual(result['events'][0]['samples'],32)

    def test_retention_and_unknown_period(self):
        self.store.write([self.sample(t) for t in range(0,64,2)],now=self.now+64)
        self.store.write([],now=self.now+31*DAY)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM insight_minutes').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM insight_events').fetchone()[0],0)
        with self.assertRaises(ValueError):self.store.performance_insights('forever')

    def test_compact_identity_does_not_store_paths_or_commands(self):
        apps=compact_apps([dict(name='python.exe',label='Python · task.py',groupKey='C:/private/project/task.py',cpu=10,memory=200,command='secret')])
        encoded=json.dumps(apps)
        self.assertNotIn('C:/private',encoded)
        self.assertNotIn('secret',encoded)
        self.assertEqual(apps[0]['label'],'Python · task.py')

    def test_average_includes_absence_and_summary_clips_window(self):
        samples=[self.sample(t) for t in range(0,64,2)]
        for sample in samples[16:]:sample['apps']={}
        self.store.write(samples,now=self.now+64)
        event=self.store.performance_insights(now=self.now+64)['events'][0]
        self.assertEqual(event['apps'][0]['cpu'],30)
        self.assertEqual(event['apps'][0]['presence'],.5)
        self.assertEqual(HistoryStore(self.path).performance_insights(now=self.now+64)['events'][0]['status'],'interrupted')


if __name__=='__main__':unittest.main()
