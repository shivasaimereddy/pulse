import sys
import logging
import platform
import zlib
import json
import os
import socket
import secrets
import sqlite3
import subprocess
import threading
import time
from collections import deque
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from . import __version__
from .database_workspace import DatabaseWorkspace, preferred_database
from .launch_options import choose_database
from .storage_tools import FolderScanner, WslStorage, allowed_path, local_roots, run_wsl
from .process_tools import checked_process, close_reason, inspect_process, process_metadata, runtime_task
from .process_snapshot import ProcessSnapshot

import psutil

ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = (Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "Pulse") if getattr(sys, "frozen", False) else ROOT / "data"
history = deque(maxlen=90)
snapshot = {}
lock = threading.Lock()
scan_save_lock = threading.Lock()
database_picker_lock = threading.Lock()
database_revision = secrets.token_hex(12)
ACTION_TOKEN = secrets.token_urlsafe(32)
MONITOR = psutil.Process()
PROTECTED_PIDS = {os.getpid(), *[p.pid for p in MONITOR.parents()]}
OWNER = MONITOR.username()
WINDOWS_DIRECTORY = Path(os.environ.get('WINDIR', 'C:/Windows')).resolve()
store = None


def can_close(process):
    return close_reason(process,PROTECTED_PIDS,OWNER,WINDOWS_DIRECTORY,os.getpid()) is None


def collect():
    global snapshot
    previous = {}
    eligibility = {}
    metadata = {}
    reader = ProcessSnapshot()
    last = time.monotonic()
    psutil.cpu_percent(None)
    while True:
        time.sleep(2)
        now = time.monotonic()
        elapsed = now - last
        last = now
        processes = []
        current = {}
        for row in reader.read():
            try:
                pid = row['pid']
                cpu_time = row['cpu_time']
                key = (pid,row['birth'])
                cpu = max(0, (cpu_time - previous.get(key, cpu_time)) / elapsed / psutil.cpu_count() * 100)
                if key not in metadata:
                    p = psutil.Process(pid)
                    canonical_created = p.create_time()
                    if pid>4 and row['created']>0 and abs(canonical_created-row['created'])>0.00001:
                        continue  # PID changed after the system snapshot.
                    eligibility[key] = can_close(p)
                    metadata[key] = dict(process_metadata(p,row['name'],OWNER,WINDOWS_DIRECTORY,os.getpid()),created=canonical_created)
                current[key] = cpu_time
                processes.append({'pid':pid, 'name':row['name'], 'memory':row['memory'], 'cpu':round(cpu,1), 'canClose':eligibility[key], **metadata[key]})
            except (psutil.Error, OSError, AttributeError):
                pass
        previous = current
        eligibility = {key: value for key, value in eligibility.items() if key in current}
        metadata = {key: value for key, value in metadata.items() if key in current}
        mem = psutil.virtual_memory()
        disks = []
        for part in psutil.disk_partitions():
            try:
                if 'cdrom' in part.opts or not part.fstype:
                    continue
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({'path': part.mountpoint, 'type': part.fstype, 'total': usage.total, 'used': usage.used, 'free': usage.free, 'percent': usage.percent})
            except OSError:
                pass
        net = psutil.net_io_counters()
        io = psutil.disk_io_counters()
        old = snapshot
        battery = psutil.sensors_battery()
        cpu = psutil.cpu_percent(None)
        sample = {'time': time.time(), 'cpu': cpu, 'memory': mem.percent}
        history.append(sample)
        data = {'timestamp': time.time(), 'hostname': socket.gethostname(), 'cpu': cpu, 'cores': psutil.cpu_count(), 'physicalCores': psutil.cpu_count(logical=False), 'memory': {'total': mem.total, 'used': mem.used, 'available': mem.available, 'percent': mem.percent}, 'disks': disks, 'processes': processes, 'history': list(history), 'uptime': time.time() - psutil.boot_time(), 'battery': {'percent': battery.percent, 'plugged': battery.power_plugged} if battery else None, 'network': {'sent': net.bytes_sent, 'received': net.bytes_recv, 'upload': max(0, (net.bytes_sent - old.get('network', {}).get('sent', net.bytes_sent)) / elapsed), 'download': max(0, (net.bytes_recv - old.get('network', {}).get('received', net.bytes_recv)) / elapsed)}, 'io': {'read': io.read_bytes if io else 0, 'write': io.write_bytes if io else 0}}
        with lock:
            data['collectorMode'] = 'windows-snapshot' if reader.native else 'compatibility'
            snapshot = data
        if store:
            store.submit(data)


def save_scan_result(result):
    # Large index transactions must not hold the live-metrics lock.
    with scan_save_lock:
        with lock:
            valid = store is not None and scan.get('updated') == result.get('updated')
        if valid:
            try:
                store.save_scan(result)
            except (OSError, sqlite3.Error) as exc:
                store.error = str(exc)
                raise


scanner = FolderScanner(lock, save_scan_result)
scan = scanner.state
wsl_storage = WslStorage()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'static'), **kwargs)

    def log_message(self, format, *args):
        logging.info(format, *args)

    def do_GET(self):
        if self.headers.get('Host') not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'):
            self.send_error(403)
            return
        path = urlparse(self.path).path
        if path == '/api/about':
            database = Path(store.path) if store is not None else DATA_ROOT / 'pulse.sqlite3'
            payload = dict(name='Pulse', version=__version__, system=platform.platform(),
                           python=platform.python_version(), architecture=platform.machine(),
                           database=str(database), recording=store is not None and store.recording_enabled and not store.error,
                           recordingEnabled=store.recording_enabled if store else False,
                           recordingError=store.error if store else None)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
            return
        if path == '/api/process':
            if self.headers.get('X-Pulse-Token') != ACTION_TOKEN:
                self.send_error(403)
                return
            try:
                query = parse_qs(urlparse(self.path).query)
                process = checked_process(query['pid'][0],query['created'][0])
                reason = close_reason(process,PROTECTED_PIDS,OWNER,WINDOWS_DIRECTORY,os.getpid())
                payload = inspect_process(process,reason)
                if process.pid == os.getpid():
                    payload['label'] = 'Pulse monitor'
                status = 200
            except psutil.NoSuchProcess:
                status,payload = 410,{'error':'This process has exited. Its PID may be used again by Windows.'}
            except (ValueError,KeyError,OverflowError) as exc:
                status,payload = 409,{'error':str(exc)}
            except (OSError,psutil.Error):
                status,payload = 403,{'error':'Windows did not allow this process to be inspected.'}
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
            return
        if path == '/api/settings':
            try:
                if store is None:
                    raise OSError('Local storage is unavailable.')
                payload, status = store.settings(), 200
                payload['storageScanning'] = bool(scan['running'])
                from .launch_options import appdata_database
                payload['defaultDatabase'] = str(appdata_database())
            except (OSError, sqlite3.Error):
                payload, status = dict(error='Settings could not be loaded.'), 503
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
            return
        if path in ('/api/activity', '/api/activity/comparison'):
            try:
                query = parse_qs(urlparse(self.path).query)
                if store is None:
                    raise OSError('Recording storage is unavailable.')
                if path.endswith('/comparison'):
                    ident = int(query.get('id', ['0'])[0])
                    if not 0 < ident <= 9223372036854775807:
                        raise ValueError('Choose a valid saved comparison.')
                    payload = store.activity_comparison(ident)
                    status = 200 if payload else 404
                    payload = payload or dict(error='This comparison is no longer retained. Refresh the activity timeline.')
                else:
                    payload = store.activity_timeline(query.get('range', ['24h'])[0])
                    status = 200
            except ValueError as exc:
                payload, status = dict(error=str(exc)), 400
            except (OSError, sqlite3.Error):
                payload, status = dict(error='The activity timeline could not be read.'), 503
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
            return
        if path == '/api/insights':
            try:
                if store is None:raise ValueError('Performance recording is unavailable.')
                period=parse_qs(urlparse(self.path).query).get('range',['24h'])[0]
                payload=store.performance_insights(period)
                payload.update(recordingError=store.error,dropped=store.dropped,recordingEnabled=store.recording_enabled)
                status=200
            except ValueError as exc:
                payload,status=dict(error=str(exc)),400
            except (OSError,sqlite3.Error):
                payload,status=dict(error='Performance insights could not be loaded.'),503
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
            return
        if path == '/api/storage/changes':
            try:
                payload=dict(locations=store.changes() if store else [])
                status=200
            except (OSError,sqlite3.Error):
                payload,status=dict(error='Storage changes could not be read.'),503
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
            return
        if path == '/api/storage/browse':
            try:
                query = parse_qs(urlparse(self.path).query)
                payload = store.browse_scan(query.get('source',[''])[0],query.get('path',[''])[0],
                    offset=min(9223372036854775807,max(0,int(query.get('offset',['0'])[0]))),search=query.get('search',[''])[0][:200],
                    minimum=min(9223372036854775807,max(0,int(query.get('minimum',['0'])[0]))),order=query.get('order',['size'])[0]) if store else None
                status = 200 if payload else 404
                payload = payload or dict(error='This folder is not in the saved index. Use Scan location to create a new scan.')
            except (OSError,sqlite3.Error,ValueError,zlib.error):
                payload,status = dict(error='The saved folder could not be read.'),503
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
            return
        if path == '/api/storage/saved':
            try:
                payload = dict(scans=[{key:value for key,value in scan.items() if key != 'changes'} for scan in store.saved_scans()] if store else [], available=store is not None)
                status = 200
            except (OSError, sqlite3.Error):
                payload, status = dict(error='Saved scans could not be read.'), 503
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
            return
        if path == '/api/storage/details':
            home = Path.home()
            scopes = [dict(name='Your user folder',path=str(home))]
            scopes.extend(dict(name=name,path=str(home/name)) for name in
                          ('Downloads','Desktop','Documents','Pictures','Videos') if (home/name).is_dir())
            scopes.extend(dict(name='Drive '+str(root),path=str(root)) for root in local_roots())
            payload = dict(scopes=scopes,wsl=wsl_storage.read())
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(body)
            return
        if path == '/api/history':
            try:
                if store is None:
                    raise ValueError('History storage is not available')
                range_key = parse_qs(urlparse(self.path).query).get('range', ['24h'])[0]
                body = json.dumps(store.query(range_key)).encode()
                self.send_response(200)
            except ValueError as exc:
                body = json.dumps({'error': str(exc)}).encode()
                self.send_response(400)
            except (OSError, sqlite3.Error):
                body = b'{"error":"History storage could not be read. Live monitoring continues."}'
                self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
            return
        if path in ('/api/metrics', '/api/storage', '/api/session'):
            with lock:
                body = json.dumps({'token': ACTION_TOKEN} if path.endswith('session') else dict(snapshot, databaseRevision=database_revision) if path.endswith('metrics') else scan).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def do_POST(self):
        if self.headers.get('Host') not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'):
            self.send_error(403)
            return
        if self.headers.get('Origin') not in (None, f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'):
            self.send_error(403)
            return
        if self.headers.get('X-Pulse-Token') != ACTION_TOKEN:
            self.send_error(403)
            return
        if self.path == '/api/action':
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length < 8192:
                    raise ValueError('Invalid request size')
                request = json.loads(self.rfile.read(length))
                action = request.get('action')
                if action == 'settings':
                    targets = {'storage': 'ms-settings:storagesense', 'startup': 'ms-settings:startupapps', 'power': 'ms-settings:powersleep', 'apps': 'ms-settings:appsfeatures'}
                    os.startfile(targets[request['target']])
                elif action == 'task-manager':
                    subprocess.Popen([str(WINDOWS_DIRECTORY / 'System32' / 'Taskmgr.exe')])
                elif action == 'process-folder':
                    process = checked_process(request['pid'],request['created'])
                    target = request.get('target','executable')
                    if target == 'executable':
                        path = process.exe()
                    elif target == 'working':
                        path = process.cwd()
                    elif target == 'script':
                        path = runtime_task(process.name(),process.cmdline(),process.cwd())['script']
                        if path is None:
                            raise ValueError('No script path is available for this process.')
                    else:
                        raise ValueError('Unknown process folder')
                    folder = allowed_path(path)
                    if not folder.is_dir():
                        folder = folder.parent
                    subprocess.Popen(['explorer.exe',str(folder)])
                elif action == 'folder':
                    target = allowed_path(request['path'])
                    if not target.is_dir():
                        target = target.parent
                    subprocess.Popen(['explorer.exe', str(target)])
                elif action == 'wsl-folder':
                    distro = request['distro']
                    linux_path = request.get('path','/')
                    if not linux_path.startswith('/') or any(part in linux_path for part in ('..','\\',':','\x00')):
                        raise ValueError('Invalid Linux folder path')
                    code, running, error = run_wsl(['--list','--running','--quiet'])
                    if code or distro not in running.splitlines():
                        raise ValueError('Start this distribution before opening its files.')
                    subprocess.Popen(['explorer.exe', '\\\\wsl.localhost\\'+distro+linux_path.replace('/','\\')])
                elif action == 'close':
                    process = psutil.Process(int(request['pid']))
                    if process.create_time() != request['created'] or not can_close(process):
                        raise ValueError('This process cannot be ended from Pulse')
                    process.terminate()
                else:
                    raise ValueError('Unknown action')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
            except (ValueError, KeyError, OSError, psutil.Error, subprocess.TimeoutExpired) as exc:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(exc)}).encode())
            return
        try:
            length = int(self.headers.get('Content-Length','0'))
            if length < 0 or length > 8192:
                raise ValueError('Invalid request size')
            request = json.loads(self.rfile.read(length)) if length else {}
            if not isinstance(request, dict):
                raise ValueError('Send a settings or action object.')
            if self.path == '/api/database/choose':
                if not database_picker_lock.acquire(blocking=False):
                    raise ValueError('A database chooser is already open. Check your taskbar.')
                try:
                    try:
                        selected = choose_database(store.path if store else None)
                    except Exception as exc:
                        logging.exception('Database file chooser failed')
                        raise RuntimeError('The Windows file chooser could not open. Close any existing chooser and try again.') from exc
                finally:
                    database_picker_lock.release()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(json.dumps({'path': selected or None}).encode())
                return
            elif self.path == '/api/database/switch':
                global database_revision
                if store is None or request.get('confirm') is not True:
                    raise ValueError('Confirm the database change.')
                if not isinstance(request.get('path'), str) or not request['path'].strip():
                    raise ValueError('Choose a database first.')
                with scan_save_lock:
                    with lock:
                        if scan['running'] or wsl_storage.state.get('scan', {}).get('running'):
                            raise ValueError('Wait for the storage scan to finish, or stop it before changing databases.')
                    saved = store.switch(request['path'])
                    with lock:
                        scan.clear()
                        scan.update(saved or dict(path=str(Path.home()), items=[], files=[], errors=0,
                                                  updated=None, visited=0, current='', cancelled=False, failure=None))
                        scan.update(running=False, saving=False)
                        database_revision = secrets.token_hex(12)
            elif self.path == '/api/settings':
                if store is None:
                    raise ValueError('Local storage is unavailable.')
                if set(request) != {'recordingEnabled'}:
                    raise ValueError('Choose a supported setting.')
                store.set_recording(request['recordingEnabled'])
            elif self.path == '/api/history/clear':
                if store is None or request.get('confirm') is not True:
                    raise ValueError('Confirm deletion of performance history.')
                store.clear_performance()
            elif self.path == '/api/storage/scan':
                with scan_save_lock:
                    scanner.start(request.get('path',str(Path.home())))
            elif self.path == '/api/storage/clear-history':
                with lock:
                    if scan['running']:
                        raise ValueError('Stop the current scan before deleting scan history.')
                with scan_save_lock:
                    with lock:
                        if scan['running']:
                            raise ValueError('Stop the current scan before deleting scan history.')
                        if store is None:
                            raise ValueError('History storage is not available.')
                    store.clear_scans()
                    with lock:
                        scan.clear()
                        scan.update(running=False, path=str(Path.home()), items=[], files=[], errors=0,
                                    updated=None, visited=0, current='', cancelled=False, failure=None)
            elif self.path == '/api/storage/cancel':
                scanner.cancel.set()
            elif self.path == '/api/storage/wsl-refresh':
                wsl_storage.refresh(force=True)
            elif self.path == '/api/storage/wsl-scan':
                wsl_storage.start_scan(request['distro'],request['path'])
            else:
                self.send_error(404)
                return
            self.send_response(202)
            self.end_headers()
        except (ValueError,KeyError,OSError,sqlite3.Error,subprocess.TimeoutExpired,RuntimeError) as exc:
            self.send_response(400)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error':str(exc)}).encode())



def create_service(port=8765, database=None):
    """Start collectors and persistence; caller owns HTTP serving and shutdown."""
    global store
    class LocalServer(ThreadingHTTPServer):
        allow_reuse_address = False

    http = LocalServer(('127.0.0.1', port), Handler)
    try:
        store = DatabaseWorkspace(database or preferred_database() or DATA_ROOT / 'pulse.sqlite3')
        saved_scan = store.latest_scan()
        if saved_scan:
            scan.update(saved_scan, running=False)
            scan['visited'] = saved_scan.get('visited')
        store.start()
        threading.Thread(target=collect, daemon=True).start()
        return http
    except Exception:
        http.server_close()
        if store is not None:
            store.close()
        raise


def main(argv=None):
    from .launch_options import database_option
    database = database_option(argv)
    if database is False:
        return
    try:
        http = create_service(database=database)
    except OSError as error:
        if getattr(error, 'winerror', None) == 10048 or getattr(error, 'errno', None) == 98:
            raise SystemExit('Pulse is already running on port 8765. Quit it before starting with a different database.') from error
        raise
    if sys.stdout is not None:
        print('Laptop dashboard: http://127.0.0.1:8765', flush=True)
        print('Database: ' + str(store.path.resolve()), flush=True)
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        store.close()
        http.server_close()
