import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pulse.history_store import HistoryStore, DAY


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'history.sqlite3'
        self.store = HistoryStore(self.path)
        self.now = 1800000000

    def tearDown(self):
        self.tmp.cleanup()

    def sample(self, timestamp=None, cpu=20, memory=40, battery=50):
        return dict(timestamp=self.now if timestamp is None else timestamp,
                    cpu=cpu,memory=memory,battery=battery,download=100,upload=20,
                    disk_free=100000,apps={'Browser':(cpu,1000)})

    def test_reopen_preserves_readings_and_peaks(self):
        self.store.write([self.sample(cpu=10),self.sample(cpu=90)],now=self.now)
        result = HistoryStore(self.path).query('1h',now=self.now+10)
        self.assertEqual(result['summary']['cpu'],50)
        self.assertEqual(result['summary']['cpuPeak'],90)
        self.assertEqual(result['points'][0]['samples'],2)
        self.assertEqual(result['apps'][0]['name'],'Browser')
        self.assertEqual(result['earliest'],self.now)
        self.assertEqual(result['lastSaved'],self.now)

    def test_weighted_average_across_buckets(self):
        self.store.write([self.sample(self.now-120,cpu=90),self.sample(cpu=0),
                          self.sample(cpu=0)],now=self.now)
        self.assertEqual(self.store.query('24h',now=self.now+1)['summary']['cpu'],30)

    def test_retention_keeps_hourly_but_expires_detail_and_apps(self):
        samples=[self.sample(self.now-days*DAY) for days in (1,10,40,370)]
        self.store.write(samples,now=self.now)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM metrics WHERE resolution=60').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM metrics WHERE resolution=3600').fetchone()[0],3)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM apps').fetchone()[0],2)

    def test_year_query_is_compact_and_preserves_peaks(self):
        self.store.write([self.sample(self.now-i*3600,cpu=i) for i in range(48)],now=self.now)
        result=self.store.query('1y',now=self.now+1)
        self.assertLessEqual(len(result['points']),3)
        self.assertEqual(result['summary']['cpuPeak'],47)
        self.assertEqual(result['resolution'],DAY)

    def test_missing_battery_and_gaps_are_not_filled(self):
        self.store.write([self.sample(self.now-600,battery=None),self.sample(battery=None)],now=self.now)
        result=self.store.query('1h',now=self.now+1)
        self.assertEqual(len(result['points']),2)
        self.assertIsNone(result['points'][0]['battery'])

    def test_scan_history_is_bounded_and_restored(self):
        for index in range(25):
            self.store.save_scan({'updated':index,'items':[{'name':'test','size':index}]})
        self.assertEqual(HistoryStore(self.path).latest_scan()['updated'],24)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM scans').fetchone()[0],20)

    def test_scans_keep_latest_per_folder_across_restart(self):
        self.store.save_scan(dict(path='C:/Desktop',updated=1,items=[dict(size=100)],totalItems=1,errors=0))
        self.store.save_scan(dict(path='C:/Downloads',updated=2,items=[dict(size=200)]))
        self.store.save_scan(dict(path='c:/desktop/',updated=3,items=[dict(size=150)]))
        saved = HistoryStore(self.path).saved_scans()
        self.assertEqual(len(saved),2)
        self.assertEqual(saved[0]['updated'],3)
        self.assertEqual(saved[0]['previous']['listedBytes'],100)
        self.assertEqual(saved[1]['path'],'C:/Downloads')

    def test_repeated_scans_do_not_evict_other_folders(self):
        self.store.save_scan(dict(path='C:/Desktop',updated=1,items=[]))
        for index in range(30):
            self.store.save_scan(dict(path='C:/Downloads',updated=index+2,items=[]))
        self.assertEqual(len(self.store.saved_scans()),2)
        for index in range(25):
            self.store.save_scan(dict(path='C:/Folder'+str(index),updated=index+40,items=[]))
        self.assertEqual(len(self.store.saved_scans()),20)

    def test_clear_scans_preserves_performance_history(self):
        self.store.write([self.sample()],now=self.now)
        self.store.save_scan(dict(path='C:/Desktop',updated=self.now,items=[]))
        self.store.clear_scans()
        reopened=HistoryStore(self.path)
        self.assertEqual(reopened.saved_scans(),[])
        self.assertIsNone(reopened.latest_scan())
        self.assertEqual(reopened.query('1h',now=self.now+1)['summary']['cpu'],20)

    def test_folder_tree_is_compressed_and_read_on_demand(self):
        self.store.save_scan(dict(path='C:/Desktop',updated=1,items=[],tree={
            'C:/Desktop/Sub':dict(items=[dict(name='a',size=12)],files=[],size=12,visited=1,errors=0,totalItems=1)}))
        reopened=HistoryStore(self.path)
        self.assertNotIn('tree',reopened.saved_scans()[0])
        result=reopened.browse_scan('c:/desktop/','c:/desktop/sub')
        self.assertEqual(result['items'][0]['size'],12)
        self.assertEqual(result['source'],'C:/Desktop')
        self.assertIsNone(reopened.browse_scan('C:/Desktop','C:/Other'))
        self.store.save_scan(dict(path='C:/Desktop',updated=2,items=[]))
        self.assertIsNone(reopened.browse_scan('C:/Desktop','C:/Desktop/Sub'))
        self.store.clear_scans()
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM scan_trees').fetchone()[0],0)

    def test_changes_identify_growth_new_missing_and_nested_files(self):
        def item(name,size,kind='file',base='C:/Downloads'):
            return dict(name=name,path=base+'/'+name,size=size,kind=kind)
        old=dict(path='C:/Downloads',updated=1,errors=0,totalItems=3,
                 items=[item('Projects',10,'folder'),item('old.zip',30),item('same',2)],
                 tree={'C:/Downloads/Projects':dict(totalItems=1,errors=0,items=[item('a.txt',10,base='C:/Downloads/Projects')])})
        new=dict(path='C:/Downloads',updated=2,errors=0,totalItems=3,
                 items=[item('Projects',25,'folder'),item('new.zip',50),item('same',2)],
                 tree={'C:/Downloads/Projects':dict(totalItems=1,errors=0,items=[item('a.txt',25,base='C:/Downloads/Projects')])})
        self.store.save_scan(old)
        self.store.save_scan(new)
        result=HistoryStore(self.path).changes()[0]['comparison']
        self.assertTrue(result['available'])
        self.assertEqual(result['net'],35)
        self.assertEqual(result['added'],65)
        self.assertEqual(result['reduced'],30)
        self.assertEqual({item['status'] for item in result['items']},{'new','missing','grown'})
        self.assertEqual(next(item for item in result['files'] if item['name']=='a.txt')['delta'],15)
        self.assertEqual(result['count'],3)
        self.store.clear_scans()
        self.assertEqual(self.store.changes(),[])

    def test_changes_explain_incomplete_snapshots_and_ignore_same_size(self):
        old=dict(path='C:/Desktop',updated=1,errors=0,totalItems=1,items=[dict(name='same',path='C:/Desktop/same',size=2)])
        new=dict(old,updated=2)
        self.assertEqual(self.store.scan_changes(old,new)['count'],0)
        result=self.store.scan_changes(old,dict(new,errors=1))
        self.assertFalse(result['available'])
        self.assertIn('unreadable',result['reason'])
        result=self.store.scan_changes(old,dict(new,totalItems=501))
        self.assertFalse(result['available'])
        self.assertIn('limited',result['reason'])
        self.store.save_scan(old)
        self.assertIsNone(self.store.changes()[0]['comparison'])

    def test_index_keeps_more_than_old_limit_and_pages_without_filesystem_reads(self):
        from pulse.scan_index import ScanIndex
        index=ScanIndex()
        try:
            root='C:/Desktop'
            for number in range(100005):
                index.add(dict(path=root+'/'+str(number)+'.dat',name=str(number)+'.dat',kind='file',size=number),root)
            index.add(dict(path=root+'/Desktop New',name='Desktop New',kind='folder',size=0,files=[],visited=0,errors=0,totalItems=0),root)
            index.add(dict(path=root,name='Desktop',kind='folder',size=1,files=[],visited=100005,errors=0,totalItems=100006),None)
            index.flush()
            self.store.save_scan(dict(path=root,updated=1,indexVersion=2,indexPath=index.path,items=[],files=[],errors=0,totalItems=100006))
        finally:
            index.close()
        reopened=HistoryStore(self.path)
        with patch('pathlib.Path.stat',side_effect=AssertionError('Browsing must not touch the filesystem')):
            node=reopened.browse_scan(root,root+'/Desktop New')
            self.assertIsNotNone(node)
            first=reopened.browse_scan(root,root)
            second=reopened.browse_scan(root,root,offset=200)
            self.assertEqual(first['nextOffset'],200)
            self.assertEqual(len(first['items']),200)
            self.assertEqual(first['filteredCount'],100006)
            self.assertFalse({item['path'] for item in first['items']} & {item['path'] for item in second['items']})
            searched=reopened.browse_scan(root,root,search='Desktop New')
            self.assertEqual(searched['items'][0]['name'],'Desktop New')
            self.assertEqual(searched['filteredCount'],1)
        self.store.clear_scans()
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM scan_entries').fetchone()[0],0)

    def test_index_rescan_changes_and_failed_replacement_preserve_snapshot(self):
        from pulse.scan_index import ScanIndex
        root='C:/Desktop'
        def save(updated,size):
            index=ScanIndex()
            try:
                index.add(dict(path=root+'/a',name='a',kind='file',size=size),root)
                for number in range(501):
                    index.add(dict(path=root+'/'+str(number),name=str(number),kind='file',size=1),root)
                index.add(dict(path=root,name='Desktop',kind='folder',size=size+501,files=[],visited=502,errors=0,totalItems=502),None)
                index.flush()
                self.store.save_scan(dict(path=root,updated=updated,indexVersion=2,indexPath=index.path,items=[],errors=0,totalItems=502))
            finally:
                index.close()
        save(1,10)
        save(2,30)
        self.assertEqual(self.store.changes()[0]['comparison']['net'],20)
        with self.assertRaises(sqlite3.OperationalError):
            self.store.save_scan(dict(path=root,updated=3,indexVersion=2,indexPath=str(self.path.parent/'missing'/'index.db'),items=[]))
        self.assertEqual(self.store.latest_scan()['updated'],2)
        self.assertEqual(self.store.browse_scan(root,root)['items'][0]['size'],30)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM scan_entries').fetchone()[0],503)

    def test_full_index_migrates_to_compact_keys_without_losing_browsing(self):
        import json
        root='C:/Desktop'
        self.store.save_scan(dict(path=root,updated=1,indexVersion=2,items=[],files=[],totalItems=1,errors=0))
        with self.store.connect() as db:
            ident=db.execute('SELECT id FROM scans').fetchone()[0]
            folder=dict(path=root,name='Desktop',kind='folder',size=12,modified=0,files=[],visited=1,errors=0,totalItems=1)
            file=dict(path=root+'/Mixed.txt',name='Mixed.txt',kind='file',size=12,modified=0)
            db.execute('CREATE TABLE scan_entries_compact (leftover TEXT)')
            db.executemany('INSERT INTO scan_entries VALUES (?,?,?,?,?,?,?,?)',[
                (ident,'c:/desktop',None,'Desktop','folder',12,0,json.dumps(folder)),
                (ident,'c:/desktop/mixed.txt','c:/desktop','Mixed.txt','file',12,0,json.dumps(file))])
        reopened=HistoryStore(self.path)
        result=reopened.browse_scan(root,root)
        self.assertEqual(result['items'][0]['path'],root+'/Mixed.txt')
        self.assertEqual(result['items'][0]['size'],12)
        with reopened.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM scan_entries WHERE typeof(key)='text'").fetchone()[0],0)
        self.assertEqual(HistoryStore(self.path).browse_scan(root,root)['totalItems'],1)

    def test_write_failure_retries_without_losing_batch(self):
        self.store.pending.put(self.sample())
        with patch.object(self.store,'write',side_effect=sqlite3.OperationalError('busy')):
            self.store.flush()
        self.assertEqual(self.store.pending.qsize(),1)
        self.assertEqual(self.store.error,'busy')
        # Use real time for retry so the test sample survives retention.
        with patch('pulse.history_store.time.time',return_value=self.now):
            self.store.flush()
        self.assertEqual(self.store.pending.qsize(),0)
        self.assertIsNone(self.store.error)

    def test_invalid_period_rejected(self):
        with self.assertRaises(ValueError):
            self.store.query('forever')


if __name__=='__main__':
    unittest.main()
