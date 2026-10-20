"""Bounded local telemetry: minute detail, hourly trends, no raw process dumps."""
import uuid
from . import performance_insights as insights
import heapq
import zlib
import json
import queue
import sqlite3
import threading
import time
from pathlib import Path
from contextlib import contextmanager
from .scan_index import entry_key, folder_payload, read_folder, read_entry

DAY = 86400
RANGES = {'1h': (3600, 60), '24h': (DAY, 60), '7d': (7 * DAY, 3600),
          '30d': (30 * DAY, 3600), '1y': (365 * DAY, DAY)}


class HistoryStore:
    def activity_timeline(self, period='24h', now=None):
        from . import activity_timeline
        with self.connect() as db:
            result = activity_timeline.query(db, period, time.time() if now is None else now, self.insight_session)
        result.update(recordingError=self.error, dropped=self.dropped, recordingEnabled=self.recording_enabled)
        return result

    def activity_comparison(self, ident):
        from . import activity_timeline
        with self.connect() as db:
            return activity_timeline.comparison(db, ident)

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.pending = queue.Queue(maxsize=120)
        self.stop = threading.Event()
        self.error = None
        self.dropped = 0
        self.last_saved = None
        self.last_cleanup = 0
        self.record_lock = threading.RLock()
        self.insight_engine = insights.InsightEngine()
        self.insight_session = uuid.uuid4().hex
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS metrics (
                    resolution INTEGER NOT NULL, bucket INTEGER NOT NULL, n INTEGER NOT NULL,
                    cpu REAL NOT NULL, cpu_peak REAL NOT NULL, memory REAL NOT NULL,
                    memory_peak REAL NOT NULL, download REAL NOT NULL, upload REAL NOT NULL,
                    disk_free REAL NOT NULL, battery REAL NOT NULL, battery_n INTEGER NOT NULL,
                    PRIMARY KEY(resolution, bucket));
                CREATE TABLE IF NOT EXISTS apps (
                    bucket INTEGER NOT NULL, name TEXT NOT NULL, cpu REAL NOT NULL,
                    memory REAL NOT NULL, n INTEGER NOT NULL, peak REAL NOT NULL,
                    PRIMARY KEY(bucket, name));
                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY, timestamp REAL NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS scan_trees (scan_id INTEGER PRIMARY KEY, payload BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS scan_entries (
                    scan_id INTEGER NOT NULL, key TEXT NOT NULL, parent TEXT, name TEXT,
                    kind TEXT, size INTEGER, modified REAL, payload BLOB,
                    PRIMARY KEY(scan_id,key));
                CREATE INDEX IF NOT EXISTS scan_entries_parent_size ON scan_entries(scan_id,parent,size DESC,key);
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                PRAGMA user_version=3;
            ''')
            insights.install(db)
            preference = db.execute("SELECT value FROM preferences WHERE key='recording'").fetchone()
            self.recording_enabled = preference is None or preference[0] != 'false'
        self.compact_entry_index()

    def settings(self):
        with self.record_lock, self.connect() as db:
            saved = db.execute("SELECT value FROM metadata WHERE key='lastSaved'").fetchone()
            size = 0
            for path in (self.path, Path(str(self.path)+'-wal'), Path(str(self.path)+'-shm')):
                try:
                    size += path.stat().st_size
                except FileNotFoundError:
                    pass
            return dict(recordingEnabled=self.recording_enabled, recordingError=self.error,
                        lastSaved=saved[0] if saved else None, database=str(self.path.resolve()),
                        databaseBytes=size, scanCount=db.execute('SELECT COUNT(*) FROM scans').fetchone()[0],
                        retention=dict(detailDays=7, trendsDays=365, appsDays=30, scanLimit=20))

    def set_recording(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('Recording must be enabled or disabled.')
        with self.record_lock:
            if enabled == self.recording_enabled:
                return
            if not enabled:
                self._flush()
                if self.error:
                    raise ValueError('Queued history could not be saved. Resolve the recording error before pausing.')
            with self.connect() as db:
                db.execute("INSERT INTO preferences VALUES ('recording',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                           ('true' if enabled else 'false',))
            self.recording_enabled = enabled
            self.insight_engine = insights.InsightEngine()
            self.insight_session = uuid.uuid4().hex

    def clear_performance(self):
        with self.record_lock:
            with self.connect() as db:
                for table in ('metrics', 'apps', 'metadata', 'insight_minutes', 'insight_events', 'insight_meta'):
                    db.execute('DELETE FROM ' + table)
            while True:
                try:
                    self.pending.get_nowait()
                except queue.Empty:
                    break
            self.insight_engine = insights.InsightEngine()
            self.insight_session = uuid.uuid4().hex
            self.last_saved = None
            self.last_cleanup = 0
            self.error = None
            self.dropped = 0

    def compact_entry_index(self):
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM scan_entries WHERE typeof(key)='text' LIMIT 1").fetchone():
                return
            # Copy sequentially and build indexes once. Updating indexed long paths
            # one by one creates excessive random writes for million-entry scans.
            db.execute('BEGIN IMMEDIATE')
            db.execute('DROP TABLE IF EXISTS scan_entries_compact')
            db.execute('CREATE TABLE scan_entries_compact (scan_id INTEGER,key BLOB,parent BLOB,name TEXT,kind TEXT,size INTEGER,modified REAL,payload BLOB)')
            cursor=db.execute('SELECT scan_id,key,parent,name,kind,size,modified,payload FROM scan_entries ORDER BY rowid')
            while True:
                rows=cursor.fetchmany(512)
                if not rows:break
                batch=[]
                for scan_id,key,parent,name,kind,size,modified,payload in rows:
                    if isinstance(key,str):
                        key=entry_key(key)
                        parent=entry_key(parent) if parent is not None else None
                        payload=folder_payload(json.loads(payload)) if kind=='folder' else b''
                    batch.append((scan_id,key,parent,name,kind,size,modified,payload))
                db.executemany('INSERT INTO scan_entries_compact VALUES (?,?,?,?,?,?,?,?)',batch)
            cursor.close()
            db.execute('DROP TABLE scan_entries')
            db.execute('ALTER TABLE scan_entries_compact RENAME TO scan_entries')
            db.execute('CREATE UNIQUE INDEX scan_entries_identity ON scan_entries(scan_id,key)')
            db.execute('CREATE INDEX scan_entries_parent_size ON scan_entries(scan_id,parent,size DESC,key)')
        with sqlite3.connect(self.path,timeout=30) as db:
            db.execute('VACUUM')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            db.execute('PRAGMA synchronous=NORMAL')
            with db:
                yield db
        finally:
            db.close()

    def start(self):
        self.worker = threading.Thread(target=self.run, daemon=True)
        self.worker.start()

    def submit(self, data):
        with self.record_lock:
            if self.recording_enabled:
                self._submit(data)

    def _submit(self, data):
        # Store only compact summaries; never retain the live process objects or paths.
        apps = {}
        for process in data['processes']:
            name = process['name'] or 'Unknown'
            cpu, memory = apps.get(name, (0, 0))
            apps[name] = (cpu + process['cpu'], memory + process['memory'])
        sample = dict(timestamp=data['timestamp'], cpu=data['cpu'],
                      memory=data['memory']['percent'], download=data['network']['download'],
                      upload=data['network']['upload'], disk_free=sum(d['free'] for d in data['disks']),
                      battery=data['battery']['percent'] if data['battery'] else None, apps=apps,
                      insightApps=insights.compact_apps(data['processes']))
        try:
            self.pending.put_nowait(sample)
        except queue.Full:
            self.dropped += 1

    def write(self, samples, now=None):
        now = time.time() if now is None else now
        candidate=self.insight_engine.clone()
        with self.connect() as db:
            insights.write(db,samples,candidate,self.insight_session,now)
            for sample in samples:
                db.execute('''INSERT INTO metadata VALUES ('firstObserved',?)
                    ON CONFLICT(key) DO UPDATE SET value=MIN(value,excluded.value)''', (sample['timestamp'],))
                db.execute('''INSERT INTO metadata VALUES ('lastSaved',?)
                    ON CONFLICT(key) DO UPDATE SET value=MAX(value,excluded.value)''', (sample['timestamp'],))
                for resolution in (60, 3600):
                    bucket = int(sample['timestamp'] // resolution) * resolution
                    db.execute('''INSERT INTO metrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(resolution,bucket) DO UPDATE SET
                        n=n+excluded.n, cpu=cpu+excluded.cpu,
                        cpu_peak=MAX(cpu_peak,excluded.cpu_peak), memory=memory+excluded.memory,
                        memory_peak=MAX(memory_peak,excluded.memory_peak),
                        download=download+excluded.download, upload=upload+excluded.upload,
                        disk_free=disk_free+excluded.disk_free, battery=battery+excluded.battery,
                        battery_n=battery_n+excluded.battery_n''',
                        (resolution, bucket, 1, sample['cpu'], sample['cpu'], sample['memory'],
                         sample['memory'], sample['download'], sample['upload'], sample['disk_free'],
                         sample['battery'] or 0, int(sample['battery'] is not None)))
                bucket = int(sample['timestamp'] // 3600) * 3600
                for name, (cpu, memory) in sample['apps'].items():
                    db.execute('''INSERT INTO apps VALUES (?,?,?,?,?,?)
                        ON CONFLICT(bucket,name) DO UPDATE SET cpu=cpu+excluded.cpu,
                        memory=memory+excluded.memory,n=n+1,peak=MAX(peak,excluded.peak)''',
                        (bucket, name, cpu, memory, 1, memory))
            if now - self.last_cleanup >= 3600:
                db.execute('DELETE FROM metrics WHERE resolution=60 AND bucket<?', (int(now-7*DAY),))
                db.execute('DELETE FROM metrics WHERE resolution=3600 AND bucket<?', (int(now-365*DAY),))
                db.execute('DELETE FROM apps WHERE bucket<?', (int(now-30*DAY),))
                self.last_cleanup = now
        self.insight_engine=candidate
        if samples:
            self.last_saved = max(s['timestamp'] for s in samples)
        self.error = None

    def run(self):
        while not self.stop.wait(10):
            self.flush()
        self.flush()

    def flush(self):
        with self.record_lock:
            self._flush()

    def _flush(self):
        samples = []
        while True:
            try:
                samples.append(self.pending.get_nowait())
            except queue.Empty:
                break
        try:
            self.write(samples)
        except (sqlite3.Error, OSError) as exc:
            self.error = str(exc)
            for sample in samples:
                try:
                    self.pending.put_nowait(sample)
                except queue.Full:
                    self.dropped += 1

    def close(self):
        self.stop.set()
        if hasattr(self, 'worker'):
            self.worker.join(timeout=8)
        else:
            self.flush()

    def performance_insights(self,period='24h',now=None):
        with self.connect() as db:
            return insights.query(db,period,time.time() if now is None else now,self.insight_session)

    def query(self, range_key, now=None):
        if range_key not in RANGES:
            raise ValueError('Choose a supported history period')
        now = time.time() if now is None else now
        duration, resolution = RANGES[range_key]
        start = int((now-duration)//resolution)*resolution
        with self.connect() as db:
            rows = db.execute('''SELECT CAST(bucket / ? AS INTEGER)*?, SUM(n), SUM(cpu)/SUM(n),
                MAX(cpu_peak), SUM(memory)/SUM(n), MAX(memory_peak), SUM(download)/SUM(n),
                SUM(upload)/SUM(n),SUM(disk_free)/SUM(n),
                CASE WHEN SUM(battery_n)>0 THEN SUM(battery)/SUM(battery_n) END
                FROM metrics WHERE resolution=? AND bucket>=? AND bucket<=?
                GROUP BY 1 ORDER BY 1''',
                (resolution, resolution, min(resolution,3600), start, now)).fetchall()
            app_rows = db.execute('''SELECT name,SUM(cpu)/SUM(n),SUM(memory)/SUM(n),MAX(peak),SUM(n)
                FROM apps WHERE bucket>=? AND bucket<=? GROUP BY name
                ORDER BY SUM(cpu)/SUM(n) DESC LIMIT 10''', (start//3600*3600, now)).fetchall()
            metadata = dict(db.execute('SELECT key,value FROM metadata').fetchall())
            earliest = metadata.get('firstObserved')
            if earliest is None:
                earliest = db.execute('SELECT MIN(bucket) FROM metrics WHERE resolution=60').fetchone()[0]
        keys = ['time', 'samples', 'cpu', 'cpuPeak', 'memory', 'memoryPeak', 'download', 'upload', 'diskFree', 'battery']
        points = [dict(zip(keys, row)) for row in rows]
        count = sum(p['samples'] for p in points)
        summary = {key: sum(p[key]*p['samples'] for p in points)/count if count else None
                   for key in ('cpu', 'memory', 'download', 'upload')}
        summary.update(cpuPeak=max((p['cpuPeak'] for p in points), default=None),
                       memoryPeak=max((p['memoryPeak'] for p in points), default=None),
                       diskChange=points[-1]['diskFree']-points[0]['diskFree'] if len(points)>1 else None)
        size = 0
        for path in (self.path, Path(str(self.path)+'-wal'), Path(str(self.path)+'-shm')):
            try:
                size += path.stat().st_size
            except FileNotFoundError:
                pass  # A WAL file can disappear as another connection checkpoints.
        return dict(points=points, summary=summary, apps=[dict(zip(['name','cpu','memory','peak','samples'], r)) for r in app_rows],
                    range=range_key, start=start, end=now, resolution=resolution, earliest=earliest,
                    databaseBytes=size, lastSaved=metadata.get('lastSaved'), error=self.error, dropped=self.dropped,
                    retention={'minutesDays':7,'hoursDays':365,'appsDays':30})

    @staticmethod
    def scan_key(path):
        return str(path).replace('\\', '/').rstrip('/').casefold()

    @classmethod
    def scan_changes(cls, previous, current, old_tree=None):
        result = dict(previousAt=previous.get('updated'),currentAt=current.get('updated'),
                      available=False,items=[],files=[],reason='')
        def complete(node):
            return not node.get('errors') and node.get('totalItems') is not None and node['totalItems'] <= 500
        if previous.get('errors') or current.get('errors'):
            result['reason']='Some entries were unreadable. Scan both times without access errors for a reliable comparison.'
            return result
        if not complete(previous) or not complete(current):
            result['reason']='One snapshot has a limited folder listing. A reliable change comparison is unavailable.'
            return result
        def compare(before, after):
            old={cls.scan_key(item['path']):item for item in before.get('items',[]) if item.get('path')}
            new={cls.scan_key(item['path']):item for item in after.get('items',[]) if item.get('path')}
            changes=[]
            for key in old.keys() | new.keys():
                a,b=old.get(key),new.get(key)
                if a and b and a['size']==b['size'] and a.get('kind')==b.get('kind'):
                    continue
                item=b or a
                changes.append(dict(name=item['name'],path=item['path'],kind=item.get('kind','file'),
                    before=a['size'] if a else 0,after=b['size'] if b else 0,
                    delta=(b['size'] if b else 0)-(a['size'] if a else 0),
                    status='new' if not a else 'missing' if not b else 'grown' if b['size']>a['size'] else 'shrunk' if b['size']<a['size'] else 'replaced'))
            return sorted(changes,key=lambda item:(-abs(item['delta']),item['path'].casefold()))
        changes=compare(previous,current)
        files=[item for item in changes if item['kind']=='file']
        old_tree=old_tree or {}
        new_tree=current.get('tree',{})
        before_nodes={cls.scan_key(path):node for path,node in old_tree.items()}
        for path,node in new_tree.items():
            key=cls.scan_key(path)
            if key==cls.scan_key(current.get('path','')):
                continue
            old=before_nodes.get(key)
            if old and complete(old) and complete(node):
                files.extend(item for item in compare(old,node) if item['kind']=='file')
        files.sort(key=lambda item:(-abs(item['delta']),item['path'].casefold()))
        result.update(available=True,items=changes[:200],files=files[:200],
            count=len(changes),fileCount=len(files),
            added=sum(item['delta'] for item in changes if item['delta']>0),
            reduced=-sum(item['delta'] for item in changes if item['delta']<0),
            net=sum(item['delta'] for item in changes),
            detailed=bool(old_tree and new_tree),
            limited=bool(previous.get('treeLimited') or current.get('treeLimited')))
        return result

    def save_scan(self, data):
        with self.connect() as db:
            rows = db.execute('SELECT id,payload FROM scans ORDER BY id DESC').fetchall()
            next_id=max((ident for ident,_ in rows),default=0)+1
            key = self.scan_key(data.get('path', ''))
            matches = [(ident,json.loads(payload)) for ident,payload in rows
                       if key and self.scan_key(json.loads(payload).get('path','')) == key]
            saved = {key:value for key,value in data.items() if key not in ('tree','indexPath')}
            if matches:
                previous = matches[0][1]
                old_row=db.execute('SELECT payload FROM scan_trees WHERE scan_id=?',(matches[0][0],)).fetchone()
                old_tree=json.loads(zlib.decompress(old_row[0])) if old_row else {}
                saved['changes']=self.scan_changes(previous,data,old_tree)

                saved['previous'] = {field: previous.get(field) for field in
                                     ('updated','visited','errors','totalItems')}
                saved['previous']['listedBytes'] = sum(item['size'] for item in previous.get('items',[]))
                db.executemany('DELETE FROM scan_trees WHERE scan_id=?', [(ident,) for ident,_ in matches])
                db.executemany('DELETE FROM scans WHERE id=?', [(ident,) for ident,_ in matches])
            cursor = db.execute('INSERT INTO scans(id,timestamp,payload) VALUES (?,?,?)', (next_id,data['updated'],json.dumps(saved)))
            if data.get('indexPath'):
                with sqlite3.connect(data['indexPath']) as source:
                    entries=source.execute('SELECT key,parent,name,kind,size,modified,payload FROM entries')
                    while True:
                        batch=entries.fetchmany(512)
                        if not batch:
                            break
                        db.executemany('INSERT INTO scan_entries VALUES (?,?,?,?,?,?,?,?)',[(next_id,*entry) for entry in batch])
                if matches and previous.get('indexVersion') == 2:
                    saved['changes']=self.index_changes(db,matches[0][0],next_id,previous,data)
                    db.execute('UPDATE scans SET payload=? WHERE id=?',(json.dumps(saved),next_id))
            if data.get('tree'):
                db.execute('INSERT INTO scan_trees(scan_id,payload) VALUES (?,?)',
                           (cursor.lastrowid,zlib.compress(json.dumps(data['tree']).encode(),level=3)))
            db.execute('DELETE FROM scans WHERE id NOT IN (SELECT id FROM scans ORDER BY id DESC LIMIT 20)')
            db.execute('DELETE FROM scan_trees WHERE scan_id NOT IN (SELECT id FROM scans)')
            db.execute('DELETE FROM scan_entries WHERE scan_id NOT IN (SELECT id FROM scans)')

    def index_changes(self, db, old_id, new_id, previous, current):
        result=dict(previousAt=previous.get('updated'),currentAt=current.get('updated'),
                    available=False,items=[],files=[],reason='')
        if previous.get('errors') or current.get('errors'):
            result['reason']='Some entries were unreadable. Scan both times without access errors for a reliable comparison.'
            return result
        query = """SELECT n.key,o.key FROM scan_entries n LEFT JOIN scan_entries o
                    ON o.scan_id=? AND n.key=o.key WHERE n.scan_id=?
                    AND (o.key IS NULL OR n.size!=o.size OR n.kind!=o.kind)
                    UNION ALL
                    SELECT NULL,o.key FROM scan_entries o LEFT JOIN scan_entries n
                    ON n.scan_id=? AND n.key=o.key WHERE o.scan_id=? AND n.key IS NULL"""
        items,files=[],[]
        count=file_count=added=reduced=0
        root=self.scan_key(current['path'])
        sequence=0
        def item_at(scan_id,key):
            if key is None:return None
            row=db.execute('SELECT name,kind,size,modified,payload,parent FROM scan_entries WHERE scan_id=? AND key=?',(scan_id,key)).fetchone()
            if row[1]=='folder':return read_entry(row[:5])
            parent=db.execute('SELECT payload FROM scan_entries WHERE scan_id=? AND key=?',(scan_id,row[5])).fetchone()
            return read_entry(row[:5],read_folder(parent[0]))
        for new_key,old_key in db.execute(query,(old_id,new_id,new_id,old_id)):
            a=item_at(old_id,old_key)
            b=item_at(new_id,new_key)
            item=b or a
            key=self.scan_key(item['path'])
            if key==root:
                continue
            delta=(b['size'] if b else 0)-(a['size'] if a else 0)
            change=dict(name=item['name'],path=item['path'],kind=item['kind'],
                        before=a['size'] if a else 0,after=b['size'] if b else 0,delta=delta,
                        status='new' if not a else 'missing' if not b else 'replaced' if a['kind']!=b['kind'] else 'grown' if delta>0 else 'shrunk')
            sequence+=1
            entry=(abs(delta),sequence,change)
            if key.rsplit('/',1)[0]==root:
                count+=1
                added+=max(0,delta)
                reduced+=max(0,-delta)
                heapq.heappush(items,entry)
                if len(items)>200:heapq.heappop(items)
            if item['kind']=='file':
                file_count+=1
                heapq.heappush(files,entry)
                if len(files)>200:heapq.heappop(files)
        result.update(available=True,items=[entry[2] for entry in sorted(items,reverse=True)],
                      files=[entry[2] for entry in sorted(files,reverse=True)],count=count,fileCount=file_count,
                      added=added,reduced=reduced,net=added-reduced,detailed=True,limited=False)
        return result

    def clear_scans(self):
        with self.connect() as db:
            db.execute('DELETE FROM scans')
            db.execute('DELETE FROM scan_trees')
            db.execute('DELETE FROM scan_entries')

    def browse_scan(self, source, path, offset=0, search='', minimum=0, order='size'):
        source_key, path_key = self.scan_key(source), self.scan_key(path)
        with self.connect() as db:
            rows = db.execute('SELECT id,payload FROM scans ORDER BY id DESC').fetchall()
            for ident,payload in rows:
                scan = json.loads(payload)
                if self.scan_key(scan.get('path','')) != source_key:
                    continue
                if scan.get('indexVersion') == 2:
                    record=db.execute('SELECT payload FROM scan_entries WHERE scan_id=? AND key=? AND kind=?',(ident,entry_key(path),'folder')).fetchone()
                    if not record:
                        return None
                    node=read_folder(record[0])
                    clause='scan_id=? AND parent=? AND size>=? AND instr(lower(name),lower(?))>0'
                    params=(ident,entry_key(path),max(0,minimum),search)
                    count=db.execute('SELECT COUNT(*) FROM scan_entries WHERE '+clause,params).fetchone()[0]
                    ordering={'size':'size DESC,key','name':'name COLLATE NOCASE,key','modified':'modified DESC,key','oldest':'modified,key'}.get(order,'size DESC,key')
                    rows=db.execute('SELECT name,kind,size,modified,payload FROM scan_entries WHERE '+clause+' ORDER BY '+ordering+' LIMIT 200 OFFSET ?',(*params,max(0,offset))).fetchall()
                    result=dict(scan)
                    result.pop('changes',None)
                    if path_key!=source_key:result.pop('previous',None)
                    result.update(node,items=[read_entry(row,node) for row in rows],source=scan['path'],
                                  path=node['path'],running=False,browsable=True,filteredCount=count,
                                  offset=offset,nextOffset=offset+len(rows) if offset+len(rows)<count else None)
                    return result
                row = db.execute('SELECT payload FROM scan_trees WHERE scan_id=?',(ident,)).fetchone()
                if not row:
                    return None
                tree = json.loads(zlib.decompress(row[0]))
                node = next((value for key,value in tree.items() if self.scan_key(key)==path_key),None)
                if node is None:
                    return None
                result = dict(scan)
                result.pop('previous',None)
                result.pop('changes',None)
                result.update(node,path=path,source=scan['path'],running=False,browsable=True)
                return result
        return None

    def saved_scans(self):
        with self.connect() as db:
            rows = db.execute('SELECT payload FROM scans ORDER BY id DESC').fetchall()
        scans = []
        seen = set()
        for row in rows:
            item = json.loads(row[0])
            key = self.scan_key(item.get('path',''))
            if key and key not in seen:
                seen.add(key)
                scans.append(item)
        return scans

    def changes(self):
        return [dict(path=scan['path'],updated=scan['updated'],comparison=scan.get('changes'))
                for scan in self.saved_scans()]

    def latest_scan(self):
        with self.connect() as db:
            row = db.execute('SELECT payload FROM scans ORDER BY id DESC LIMIT 1').fetchone()
        return json.loads(row[0]) if row else None
