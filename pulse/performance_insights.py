"""Local performance observations. No process paths, commands or retrospective claims."""
import copy
import hashlib
import json
import uuid

DAY=86400
THRESHOLDS={'cpu':75,'memory':80}
MIN_DURATION=60
MAX_GAP=10


def compact_apps(processes):
    groups={}
    for process in processes:
        name=process.get('name') or 'Unknown'
        identity=hashlib.sha256(str(process.get('groupKey') or name).encode(errors='replace')).hexdigest()[:24]
        app=groups.setdefault(identity,dict(id=identity,name=name,label=process.get('label') or name,cpu=0,memory=0))
        app['cpu']+=process.get('cpu',0)
        app['memory']+=process.get('memory',0)
    return list(groups.values())


class InsightEngine:
    def __init__(self):
        self.active={}
        self.last=None

    @staticmethod
    def qualified(event):
        duration=event['end']-event['start']
        return duration>=MIN_DURATION and event['n']>=25 and event['n']*2/duration>=.8

    def clone(self):
        return copy.deepcopy(self)

    def feed(self,sample,session):
        timestamp=sample['timestamp']
        changes=[]
        # Do not join observations across sleep, missing samples, clock jumps, or restarts.
        if self.last is not None and (timestamp<=self.last or timestamp-self.last>MAX_GAP):
            for event in self.active.values():
                if self.qualified(event):
                    changes.append(self.record(event,'interrupted'))
            self.active={}
        self.last=timestamp
        apps=sample.get('insightApps') or [dict(id=name,name=name,label=name,cpu=value[0],memory=value[1]) for name,value in sample.get('apps',{}).items()]
        for kind,threshold in THRESHOLDS.items():
            event=self.active.get(kind)
            if sample[kind]<threshold:
                if event and self.qualified(event):
                    changes.append(self.record(event,'ended'))
                self.active.pop(kind,None)
                continue
            if event is None:
                event=dict(id=uuid.uuid4().hex,session=session,kind=kind,start=timestamp,end=timestamp,
                           n=0,total=0,peak=0,apps={})
                self.active[kind]=event
            event['end']=timestamp
            event['n']+=1
            event['total']+=sample[kind]
            event['peak']=max(event['peak'],sample[kind])
            for app in apps:
                entry=event['apps'].setdefault(app['id'],dict(id=app['id'],name=app['name'],label=app.get('label') or app['name'],cpu=0,memory=0,peakMemory=0,present=0))
                entry['cpu']+=app['cpu']
                entry['memory']+=app['memory']
                entry['peakMemory']=max(entry['peakMemory'],app['memory'])
                entry['present']+=1
            if len(event['apps'])>64:
                rank='cpu' if kind=='cpu' else 'memory'
                event['apps']=dict(sorted(event['apps'].items(),key=lambda item:item[1][rank],reverse=True)[:64])
            if self.qualified(event):
                changes.append(self.record(event,'active'))
        return changes

    @staticmethod
    def record(event,status):
        apps=[dict(id=app['id'],name=app['name'],label=app['label'],cpu=app['cpu']/event['n'],
                   memory=app['memory']/event['n'],peakMemory=app['peakMemory'],presence=app['present']/event['n']) for app in event['apps'].values()]
        rank='cpu' if event['kind']=='cpu' else 'memory'
        apps.sort(key=lambda app:app[rank],reverse=True)
        return dict(id=event['id'],session=event['session'],kind=event['kind'],start=event['start'],end=event['end'],
                    samples=event['n'],average=event['total']/event['n'],peak=event['peak'],status=status,apps=apps[:5])


def install(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS insight_minutes (
        bucket INTEGER PRIMARY KEY,n INTEGER NOT NULL,cpu REAL NOT NULL,memory REAL NOT NULL,
        cpu_peak REAL NOT NULL,memory_peak REAL NOT NULL,apps TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS insight_events (
        id TEXT PRIMARY KEY,start REAL NOT NULL,end REAL NOT NULL,payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS insight_events_end ON insight_events(end);
        CREATE TABLE IF NOT EXISTS insight_meta (key TEXT PRIMARY KEY,value REAL NOT NULL);''')


def write(db,samples,engine,session,now):
    for sample in samples:
        timestamp=sample['timestamp']
        db.execute("INSERT INTO insight_meta VALUES ('since',?) ON CONFLICT(key) DO UPDATE SET value=MIN(value,excluded.value)",(timestamp,))
        db.execute("INSERT INTO insight_meta VALUES ('last',?) ON CONFLICT(key) DO UPDATE SET value=MAX(value,excluded.value)",(timestamp,))
        bucket=int(timestamp//60)*60
        apps=sample.get('insightApps',[])
        top={app['id']:app for app in sorted(apps,key=lambda app:app['cpu'],reverse=True)[:5]+sorted(apps,key=lambda app:app['memory'],reverse=True)[:5]}
        previous=db.execute('SELECT apps FROM insight_minutes WHERE bucket=?',(bucket,)).fetchone()
        combined=json.loads(previous[0]) if previous else {}
        for app in top.values():
            record=combined.setdefault(app['id'],dict(id=app['id'],name=app['name'],label=app.get('label') or app['name'],cpu=0,memory=0,peakMemory=0,present=0))
            record['cpu']+=app['cpu'];record['memory']+=app['memory'];record['present']+=1
            record['peakMemory']=max(record['peakMemory'],app['memory'])
        # Keep at most 20 candidates per minute, including both CPU and memory leaders.
        ids={app['id'] for app in sorted(combined.values(),key=lambda app:app['cpu'],reverse=True)[:10]+sorted(combined.values(),key=lambda app:app['memory'],reverse=True)[:10]}
        combined={key:value for key,value in combined.items() if key in ids}
        db.execute('''INSERT INTO insight_minutes VALUES (?,?,?,?,?,?,?) ON CONFLICT(bucket) DO UPDATE SET
            n=n+1,cpu=cpu+excluded.cpu,memory=memory+excluded.memory,
            cpu_peak=MAX(cpu_peak,excluded.cpu_peak),memory_peak=MAX(memory_peak,excluded.memory_peak),apps=excluded.apps''',
            (bucket,1,sample['cpu'],sample['memory'],sample['cpu'],sample['memory'],json.dumps(combined)))
        for event in engine.feed(sample,session):
            db.execute('INSERT INTO insight_events VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET end=excluded.end,payload=excluded.payload',
                       (event['id'],event['start'],event['end'],json.dumps(event)))
    db.execute('DELETE FROM insight_minutes WHERE bucket<?',(now-7*DAY,))
    db.execute('DELETE FROM insight_events WHERE end<?',(now-30*DAY,))
    db.execute('DELETE FROM insight_events WHERE id NOT IN (SELECT id FROM insight_events ORDER BY end DESC LIMIT 2000)')


def query(db,period,now,session):
    ranges={'1h':3600,'24h':DAY,'7d':7*DAY}
    if period not in ranges:raise ValueError('Choose one hour, 24 hours, or seven days.')
    start=now-ranges[period]
    meta=dict(db.execute('SELECT key,value FROM insight_meta'))
    rows=db.execute('SELECT payload FROM insight_events WHERE end>=? AND start<=? ORDER BY end DESC LIMIT 201',(start,now)).fetchall()
    events=[]
    for row in rows[:200]:
        event=json.loads(row[0])
        if event['status']=='active' and (event['session']!=session or now-event['end']>MAX_GAP):event['status']='interrupted'
        event.pop('session',None)
        events.append(event)
    resolution={'1h':60,'24h':300,'7d':1800}[period]
    points=[dict(time=row[0],samples=row[1],cpu=row[2]/row[1],memory=row[3]/row[1],cpuPeak=row[4],memoryPeak=row[5],coverage=min(resolution,row[1]*2))
            for row in db.execute('SELECT CAST(bucket / ? AS INTEGER)*?,SUM(n),SUM(cpu),SUM(memory),MAX(cpu_peak),MAX(memory_peak) FROM insight_minutes WHERE bucket>=? AND bucket<=? GROUP BY 1 ORDER BY 1',(resolution,resolution,int(start//60)*60,now))]
    repeated={}
    for event in sorted(events,key=lambda event:event['start']):
        for app in event['apps']:
            key=app['id']
            target=repeated.setdefault(key,dict(id=key,name=app['name'],label=app['label'],events=0,cpuEvents=0,memoryEvents=0,peakMemory=0,lastEnd=None))
            if target['lastEnd'] is None or event['start']>target['lastEnd']:target['events']+=1
            target['lastEnd']=max(target['lastEnd'] or 0,event['end'])
            target[event['kind']+'Events']+=1;target['peakMemory']=max(target['peakMemory'],app['peakMemory'])
    frequent=sorted((app for app in repeated.values() if app['events']>=2),key=lambda app:-app['events'])[:5]
    for app in frequent:app.pop('lastEnd',None)
    return dict(period=period,resolution=resolution,start=start,end=now,since=meta.get('since'),lastSaved=meta.get('last'),events=events,points=points,
                repeated=frequent,truncated=len(rows)>200,thresholds=THRESHOLDS,minimumSeconds=MIN_DURATION,
                summary=dict(events=len(events),cpuSeconds=sum(max(0,min(now,event['end'])-max(start,event['start'])) for event in events if event['kind']=='cpu'),
                             memorySeconds=sum(max(0,min(now,event['end'])-max(start,event['start'])) for event in events if event['kind']=='memory')))
