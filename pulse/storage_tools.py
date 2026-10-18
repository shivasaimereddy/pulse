"""Read-only storage inspection, isolated from the live metrics collector."""
import sqlite3
import ctypes
import heapq
import os
import re
import subprocess
import threading
import time
from pathlib import Path

import psutil
from .scan_index import ScanIndex


def local_roots():
    return [Path(p.mountpoint).resolve() for p in psutil.disk_partitions()
            if p.fstype and 'cdrom' not in p.opts and not p.mountpoint.startswith('\\\\')]


def allowed_path(value):
    # Do not turn a user-entered network path into an implicit network connection.
    if not value or str(value).startswith(('\\\\', '//')):
        raise ValueError('Choose a local Windows folder or use the WSL tab.')
    target = Path(value).resolve(strict=True)
    if not any(target == root or root in target.parents for root in local_roots()):
        raise ValueError('Choose a folder on a connected local drive.')
    return target


class FolderScanner:
    def __init__(self, lock, save):
        self.lock = lock
        self.save = save
        self.cancel = threading.Event()
        self.state = dict(running=False, path=str(Path.home()), items=[], files=[], errors=0,
                          updated=None, visited=0, current='', cancelled=False, failure=None)
        self.file_heap = []
        self.sequence = 0
        self.last_progress = 0

    def start(self, value):
        target = allowed_path(value)
        if not target.is_dir():
            raise ValueError('Choose a folder to scan.')
        with self.lock:
            if self.state['running']:
                raise ValueError('Stop the current scan before starting another.')
            self.cancel.clear()
            self.state.update(running=True, path=str(target), items=[], files=[], errors=0,
                              visited=0, current='', cancelled=False, failure=None, updated=None, browsable=False, treeLimited=False, totalItems=0, indexVersion=0, size=0)
            self.file_heap = []
            self.sequence = 0
        threading.Thread(target=self.run, args=(target,), daemon=True).start()

    def add_file(self, entry, stat):
        self.sequence += 1
        item = dict(name=entry.name, path=entry.path, size=stat.st_size,
                    kind='file', modified=stat.st_mtime)
        heapq.heappush(self.file_heap, (stat.st_size, self.sequence, item))
        if len(self.file_heap) > 50:
            heapq.heappop(self.file_heap)

    def largest_files(self):
        return [item[2] for item in sorted(self.file_heap, reverse=True)]

    def run(self, target):
        # Iterative depth-first traversal: one filesystem read, with totals propagated
        # upward as each directory finishes. Stream every entry to a disk-backed index.
        try:
            index = ScanIndex()
        except (OSError,sqlite3.Error) as exc:
            with self.lock:
                self.state.update(running=False,failure='Scan index could not be created: '+str(exc))
            return
        self.state['path']=str(target)
        root = {}
        visited = errors = 0
        def frame(path):
            return dict(path=str(path), entries=None, size=0, visited=0, errors=0,
                        items=[], files=[], totalItems=0)
        stack = [frame(target)]
        try:
            while stack and not self.cancel.is_set():
                node = stack[-1]
                if node['entries'] is None:
                    try:
                        node['entries'] = os.scandir(node['path'])
                    except OSError:
                        node['errors'] += 1
                        errors += 1
                        node['entries'] = iter(())
                try:
                    entry = next(node['entries'])
                except StopIteration:
                    iterator = node['entries']
                    if hasattr(iterator,'close'):
                        iterator.close()
                    stack.pop()
                    node['items'].sort(key=lambda item:item['size'], reverse=True)
                    node['files'].sort(key=lambda item:item['size'], reverse=True)
                    summary = {key:node[key] for key in ('files','size','visited','errors','totalItems')}
                    identity = node.get('identity',dict(name=Path(node['path']).name,path=node['path'],kind='folder',modified=0))
                    index.add(dict(identity,**summary),stack[-1]['path'] if stack else None)
                    if not stack:
                        root = dict(summary,items=node['items'])
                    if stack:
                        parent = stack[-1]
                        parent['size'] += node['size']
                        parent['visited'] += node['visited']
                        parent['errors'] += node['errors']
                        item = node['identity']
                        item['size'] = node['size']
                        parent['items'].append(item)
                        parent['items'].sort(key=lambda item:item['size'],reverse=True)
                        del parent['items'][500:]
                        parent['files'] = sorted(parent['files']+node['files'],key=lambda item:item['size'],reverse=True)[:50]
                    continue
                try:
                    stat = entry.stat(follow_symlinks=False)
                    if entry.is_symlink() or getattr(stat,'st_file_attributes',0) & 1024:
                        continue
                    if entry.path == index.temp.name:
                        continue
                    directory = entry.is_dir(follow_symlinks=False)
                    item = dict(name=entry.name,path=entry.path,size=stat.st_size,
                                kind='folder' if directory else 'file',modified=stat.st_mtime)
                    node['totalItems'] += 1
                    if directory:
                        child = frame(entry.path)
                        child['identity'] = item
                        stack.append(child)
                    else:
                        visited += 1
                        node['visited'] += 1
                        node['size'] += item['size']
                        self.add_file(entry,stat)
                        index.add(item,node['path'])
                        node['items'].append(item)
                        # Bound per-directory lists, including during traversal.
                        if len(node['items']) > 500:
                            node['items'].sort(key=lambda item:item['size'],reverse=True)
                            del node['items'][500:]
                        node['files'] = sorted(node['files']+[item],key=lambda item:item['size'],reverse=True)[:50]
                except OSError:
                    errors += 1
                    node['errors'] += 1
                if time.monotonic()-self.last_progress > .5:
                    with self.lock:
                        self.state.update(current=node['path'],visited=visited,errors=errors,
                            size=sum(open_node['size'] for open_node in stack),
                            items=sorted(stack[0]['items'],key=lambda item:item['size'],reverse=True),
                            files=self.largest_files(),totalItems=stack[0]['totalItems'])
                    self.last_progress = time.monotonic()
        except (OSError, sqlite3.Error) as exc:
            with self.lock:
                self.state['failure'] = str(exc)
        finally:
            for node in stack:
                iterator = node['entries']
                if hasattr(iterator,'close'):
                    iterator.close()
            with self.lock:
                self.state.update(running=True,saving=True,current='',cancelled=self.cancel.is_set(),updated=time.time(),
                    visited=visited,errors=errors,items=root.get('items',self.state['items']),
                    files=self.largest_files(),totalItems=root.get('totalItems',self.state.get('totalItems',0)),
                    browsable=bool(root),treeLimited=False,indexVersion=2,size=root.get('size',0))
                saved = dict(self.state,running=False,saving=False)
                saved['indexPath'] = index.path
            try:
                if not saved['cancelled'] and not saved['failure']:
                    index.flush()
                    self.save(saved)
            except (OSError,sqlite3.Error) as exc:
                with self.lock:
                    self.state['failure'] = 'Scan index could not be saved: '+str(exc)
            finally:
                index.close()
                with self.lock:
                    self.state.update(running=False,saving=False)


def decode_output(value):
    return value.decode('utf-16-le' if b'\x00' in value[:80] else 'utf-8', errors='replace').lstrip('\ufeff').strip()


def run_wsl(args, timeout=12):
    result = subprocess.run(['wsl.exe', *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=timeout, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return result.returncode, decode_output(result.stdout), decode_output(result.stderr)


def parse_df(text):
    mounts = []
    for line in text.splitlines()[1:]:
        fields = line.split(None, 6)
        if len(fields) != 7:
            continue
        source, filesystem, total, used, free, percent, mount = fields
        try:
            if mount != '/' and not mount.startswith('/mnt/'):
                continue
            if filesystem in ('tmpfs','overlay','rootfs','devtmpfs','squashfs'):
                continue
            windows = bool(re.match(r'^[A-Za-z]:', source)) or filesystem == 'drvfs'
            mounts.append(dict(source=source, type=filesystem, path=mount, total=int(total),
                               used=int(used), free=int(free), percent=float(percent.rstrip('%')),
                               windows=windows, shared=False))
        except ValueError:
            continue
    root = next((m for m in mounts if m['path']=='/'), None)
    for mount in mounts:
        mount['shared'] = bool(root and mount['path']!='/' and mount['source']==root['source'])
    return mounts


def virtual_disk(path):
    stat = path.stat()
    allocated = None
    if os.name == 'nt':
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        get_size = kernel.GetCompressedFileSizeW
        get_size.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
        get_size.restype = wintypes.DWORD
        high = wintypes.DWORD()
        ctypes.set_last_error(0)
        low = get_size(str(path), ctypes.byref(high))
        if low != 0xffffffff or ctypes.get_last_error() == 0:
            allocated = (high.value << 32) | low
    return dict(path=str(path), fileBytes=stat.st_size, allocatedBytes=allocated)


def registered_distros():
    if os.name != 'nt':
        return []
    import winreg
    rows = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Lxss') as key:
            for index in range(winreg.QueryInfoKey(key)[0]):
                with winreg.OpenKey(key,winreg.EnumKey(key,index)) as distro:
                    def value(name, default=None):
                        try:
                            return winreg.QueryValueEx(distro,name)[0]
                        except OSError:
                            return default
                    base = value('BasePath')
                    row = dict(name=value('DistributionName'),version=value('Version',2), disk=None)
                    if base:
                        disk = Path(base) / value('VhdFileName','ext4.vhdx')
                        try:
                            row['disk'] = virtual_disk(disk)
                        except OSError:
                            pass
                    if row['name']:
                        rows.append(row)
    except FileNotFoundError:
        pass
    return rows


class WslStorage:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = dict(running=False, updated=None, error=None, distros=[], extraDisks=[],
                          scan=dict(running=False,items=[],distro=None,path=None,error=None))

    def refresh(self, force=False):
        with self.lock:
            if self.state['running'] or (not force and self.state['updated'] and time.time()-self.state['updated']<60):
                return
            self.state['running'] = True
        threading.Thread(target=self.inspect,daemon=True).start()

    def read(self):
        self.refresh()
        with self.lock:
            return dict(self.state)

    def inspect(self):
        rows = []
        extras = []
        error = None
        try:
            rows = registered_distros()
            code, output, stderr = run_wsl(['--list','--running','--quiet'])
            if code:
                raise ValueError(stderr or output or 'WSL is unavailable.')
            running = set(output.splitlines())
            for row in rows:
                row.update(running=row['name'] in running, mounts=[], error=None)
                if row['running']:
                    try:
                        code, output, stderr = run_wsl(['--distribution',row['name'],'--exec','env','LC_ALL=C','df','-P','-B1','-T'])
                        if code:
                            raise ValueError(stderr or output)
                        row['mounts'] = parse_df(output)
                    except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
                        row['error'] = str(exc)
            # Docker's data VHD can be separate from its registered distro disk.
            docker = Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData'/'Local'))) / 'Docker' / 'wsl'
            known = {os.path.normcase(d['disk']['path']) for d in rows if d['disk']}
            for candidate in (docker/'disk'/'docker_data.vhdx',docker/'data'/'ext4.vhdx'):
                try:
                    if os.path.normcase(str(candidate)) not in known:
                        extras.append(dict(name='Docker data',**virtual_disk(candidate)))
                except OSError:
                    pass
        except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
            error = str(exc)
        with self.lock:
            self.state.update(running=False,updated=time.time(),error=error,distros=rows,extraDisks=extras)

    def start_scan(self, distro, path):
        if path not in ('/home','/var','/usr','/opt'):
            raise ValueError('Choose one of the supported Linux folders.')
        # Recheck at action time; do not deliberately launch a stopped distro.
        code, output, error = run_wsl(['--list','--running','--quiet'])
        if code or distro not in output.splitlines():
            raise ValueError('Start this distribution yourself before scanning it.')
        with self.lock:
            if self.state['scan']['running']:
                raise ValueError('A Linux scan is already running.')
            self.state['scan'] = dict(running=True,items=[],distro=distro,path=path,error=None)
        threading.Thread(target=self.scan,args=(distro,path),daemon=True).start()

    def scan(self, distro, path):
        items = []
        error = None
        try:
            code, output, stderr = run_wsl(['--distribution',distro,'--exec','env','LC_ALL=C','du','-x','-B1','--max-depth=1','--',path],timeout=90)
            for line in output.splitlines():
                fields = line.split('\t',1)
                if len(fields)==2 and fields[0].isdigit():
                    items.append(dict(size=int(fields[0]),path=fields[1]))
            if code:
                error = 'Some entries could not be read; these results may be incomplete.' if items else stderr or 'No readable folders.'
        except (OSError,subprocess.TimeoutExpired) as exc:
            error = 'Scan timed out after 90 seconds. Try a smaller folder.' if isinstance(exc,subprocess.TimeoutExpired) else str(exc)
        with self.lock:
            self.state['scan'] = dict(running=False,items=sorted(items,key=lambda x:x['size'],reverse=True),
                                      distro=distro,path=path,error=error,updated=time.time())
