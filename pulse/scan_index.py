"""Disk-backed scan staging. Buffer only a small write batch, never the whole tree."""
import hashlib
import zlib
import json
import sqlite3
import tempfile
from pathlib import Path


def path_key(path):
    return str(path).replace('\\', '/').rstrip('/').casefold()


def entry_key(path):
    return hashlib.sha256(path_key(path).encode('utf-8',errors='surrogatepass')).digest()


def folder_payload(item):
    return zlib.compress(json.dumps(item).encode(),level=3)


def read_folder(payload):
    return json.loads(zlib.decompress(payload) if isinstance(payload,bytes) else payload)


def read_entry(row, parent=None):
    name,kind,size,modified,payload=row
    if kind=='folder':
        folder=read_folder(payload)
        return {field:folder.get(field) for field in ('name','path','kind','size','modified')}
    path=parent['path']
    separator='\\' if '\\' in path else '/'
    return dict(name=name,kind=kind,size=size,modified=modified,
                path=path.rstrip('\\/')+separator+name)


class ScanIndex:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pulse-scan-')
        self.path = str(Path(self.temp.name) / 'index.sqlite3')
        self.db = sqlite3.connect(self.path)
        # Staging is disposable; only the final history transaction needs durability.
        self.db.execute('PRAGMA journal_mode=OFF')
        self.db.execute('PRAGMA synchronous=OFF')
        self.db.execute('CREATE TABLE entries (key TEXT PRIMARY KEY,parent TEXT,name TEXT,kind TEXT,size INTEGER,modified REAL,payload BLOB)')
        self.pending = []

    def add(self, item, parent):
        self.pending.append((entry_key(item['path']),entry_key(parent) if parent is not None else None,
                             item['name'],item['kind'],item['size'],item.get('modified',0),folder_payload(item) if item['kind']=='folder' else b''))
        if len(self.pending) >= 512:
            self.flush()

    def flush(self):
        if self.pending:
            self.db.executemany('INSERT INTO entries VALUES (?,?,?,?,?,?,?)',self.pending)
            self.db.commit()
            self.pending.clear()

    def close(self):
        self.db.close()
        self.temp.cleanup()
