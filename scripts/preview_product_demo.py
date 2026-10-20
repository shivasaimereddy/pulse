"""Render the real interface with fictional data for public product screenshots.

This preview never collects system metrics or accepts actions. Its database is
temporary and is removed when the server exits.
"""
import json
import math
from pathlib import Path
import sys
import tempfile
import time
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pulse import server
from pulse.history_store import HistoryStore

GB = 1024 ** 3
now = time.time()


class DemoHandler(server.Handler):
    def do_POST(self):
        self.send_error(403, 'Screenshot preview is read-only')

    def do_GET(self):
        route = urlparse(self.path).path
        if route == '/api/metrics':
            payload = dict(server.snapshot, timestamp=time.time())
        elif route == '/api/storage/details':
            payload = dict(scopes=[dict(name='Projects', path='C:/Projects'), dict(name='Drive C:', path='C:/')],
                           wsl=dict(distros=[], extraDisks=[], running=False, updated=now, error=None, scan=dict(running=False, items=[], errors=0)))
        else:
            return super().do_GET()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())


def main():
    with tempfile.TemporaryDirectory(prefix='pulse-product-preview-') as directory:
        server.store = HistoryStore(Path(directory) / 'demo.db')
        samples = []
        for i in range(720):
            busy = 230 <= i <= 275 or 540 <= i <= 565
            samples.append(dict(timestamp=now-(719-i)*60, cpu=86 if busy else 18+12*math.sin(i/13),
                                memory=88 if busy else 52+5*math.sin(i/35), battery=84,
                                download=1400000, upload=240000, disk_free=285*GB,
                                apps={'Visual Studio Code': (31 if busy else 8, 2.4*GB),
                                      'Microsoft Edge': (27 if busy else 5, 3.1*GB), 'Docker Desktop': (19 if busy else 3, 1.8*GB)}))
        server.store.write(samples, now=now)
        server.store.last_saved = now
        items = [dict(name=name, path='C:/Projects/'+name, size=size*GB, kind='folder', modified=now-86400)
                 for name, size in [('Web applications', 42), ('Build artifacts', 26), ('Design assets', 18), ('Archives', 12), ('Documentation', 4)]]
        for age, growth in [(86400*4, 0), (0, 7)]:
            rows = [dict(item) for item in items]
            rows[1]['size'] += growth*GB
            saved = server.store.save_scan(dict(path='C:/Projects', updated=now-age, items=rows,
                files=[dict(name='release-assets.zip', path='C:/Projects/Archives/release-assets.zip', size=4.2*GB, kind='file', modified=now-86400)],
                errors=0, totalItems=5, size=sum(r['size'] for r in rows), visited=18452, browsable=True,
                tree={r['path']:dict(items=[], files=[], size=r['size'], visited=3000, errors=0, totalItems=0) for r in rows}))
        server.scan.update(server.store.latest_scan(), running=False)
        processes = []
        for index, (name, label, cpu, memory, count) in enumerate([
            ('Code.exe','Visual Studio Code',12.4,2.4,8), ('msedge.exe','Microsoft Edge',7.2,3.1,12),
            ('Docker Desktop.exe','Docker Desktop',3.4,1.8,4), ('Figma.exe','Figma',1.8,0.8,3),
            ('explorer.exe','Windows Explorer',0.7,0.2,1), ('Pulse.exe','Pulse',0.4,0.08,1)]):
            for part in range(count):
                processes.append(dict(pid=1000+index*100+part, created=now-5000, name=name, label=label,
                    cpu=cpu/count, memory=memory*GB/count, canClose=name!='Pulse.exe', mine=True,
                    system=False, executable='C:/Applications/'+name, task=label))
        server.snapshot = dict(timestamp=now, hostname='WORKSPACE', cpu=26.1, cores=16, physicalCores=8,
            memory=dict(total=32*GB, used=18.2*GB, available=13.8*GB, percent=56.9),
            disks=[dict(path='C:\\', type='NTFS', total=953*GB, used=668*GB, free=285*GB, percent=70.1)],
            processes=processes, history=[dict(time=now-(89-i)*2, cpu=24+8*math.sin(i/5), memory=56+2*math.sin(i/9)) for i in range(90)],
            uptime=29340, battery=dict(percent=84, plugged=True),
            network=dict(sent=2*GB, received=12*GB, upload=240000, download=1400000), io=dict(read=90*GB, write=32*GB))
        with ThreadingHTTPServer(('127.0.0.1', 8788), DemoHandler) as httpd:
            print('Fictional product preview: http://127.0.0.1:8788/', flush=True)
            httpd.serve_forever()


if __name__ == '__main__':
    main()
