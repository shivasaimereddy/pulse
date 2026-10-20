"""Read-only activity projections over retained local records."""
import json

from . import performance_insights

PERIODS = {'1h': 3600, '24h': 86400, '7d': 604800}


def recording_gaps(buckets, start, end, since):
    """Only whole missing minute buckets, after recording first began."""
    if since is None:
        return []
    cursor = max(start, since)
    gaps = []
    for bucket in buckets:
        if bucket > cursor and bucket - cursor >= 120:
            gaps.append(dict(id=f'gap:{int(cursor)}:{int(bucket)}', kind='gap',
                             start=cursor, end=min(bucket, end)))
        cursor = max(cursor, bucket + 60)
    if end - cursor >= 120:
        gaps.append(dict(id=f'gap:{int(cursor)}:{int(end)}', kind='gap', start=cursor, end=end))
    return gaps


def query(db, period, now, session):
    if period not in PERIODS:
        raise ValueError('Choose one hour, 24 hours, or seven days.')
    start = now - PERIODS[period]
    observations = performance_insights.query(db, period, now, session)
    events = [dict(id='performance:' + event['id'], kind='performance',
                   start=event['start'], end=event['end'], observation=event)
              for event in observations['events']]
    for ident, payload in db.execute('SELECT id,payload FROM scans ORDER BY id DESC LIMIT 20'):
        scan = json.loads(payload)
        comparison = scan.get('changes') or {}
        timestamp = comparison.get('currentAt')
        if (not comparison.get('available') or timestamp is None or not start <= timestamp <= now
                or not (comparison.get('count') or comparison.get('fileCount'))):
            continue
        events.append(dict(id=f'storage:{ident}', kind='storage', scanId=ident,
                           path=scan['path'], start=comparison['previousAt'], end=timestamp,
                           comparison={key: comparison.get(key) for key in
                                       ('net', 'added', 'reduced', 'count', 'fileCount', 'limited')},
                           highlights=comparison.get('items', [])[:3]))
    buckets = [row[0] for row in db.execute(
        'SELECT bucket FROM insight_minutes WHERE bucket>=? AND bucket<=? ORDER BY bucket',
        (int(start // 60) * 60, now))]
    events.extend(recording_gaps(buckets, start, now, observations['since']))
    events.sort(key=lambda event: (-event['end'], event['id']))
    truncated = len(events) > 300 or observations['truncated']
    events = events[:300]
    summary = {kind: sum(event['kind'] == kind for event in events)
               for kind in ('performance', 'storage', 'gap')}
    return dict(period=period, start=start, end=now, events=events[:300], summary=summary,
                lastSaved=observations['lastSaved'], since=observations['since'],
                truncated=truncated)


def comparison(db, ident):
    row = db.execute('SELECT payload FROM scans WHERE id=?', (ident,)).fetchone()
    if not row:
        return None
    scan = json.loads(row[0])
    if not (scan.get('changes') or {}).get('available'):
        return None
    return dict(path=scan['path'], comparison=scan['changes'])
