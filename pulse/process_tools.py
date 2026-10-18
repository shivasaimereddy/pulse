"""Process identity and on-demand inspection. Commands are never persisted."""
import math
import os
import re
import subprocess
from pathlib import Path

import psutil

FRIENDLY = {'chrome.exe':'Google Chrome','msedge.exe':'Microsoft Edge','chatgpt.exe':'ChatGPT',
            'code.exe':'Visual Studio Code','explorer.exe':'Windows Explorer',
            'svchost.exe':'Windows Service Host','dwm.exe':'Desktop Window Manager',
            'msmpeng.exe':'Microsoft Defender','wsl.exe':'Windows Subsystem for Linux',
            'windowsterminal.exe':'Windows Terminal','docker desktop.exe':'Docker Desktop'}
SECRET = re.compile(r'(?:password|passwd|secret|token|api[-_]?key|authorization|credential)',re.I)


def redact_command(args):
    """Best-effort common secret-flag / key-value / URL credential masking."""
    result=[]
    hide_next=False
    for arg in args:
        if hide_next:
            result.append('[hidden]')
            hide_next=False
            continue
        value=str(arg)
        if value.startswith('-') and SECRET.search(value):
            if '=' in value:
                value=value.split('=',1)[0]+'=[hidden]'
            elif ':' in value:
                value=value.split(':',1)[0]+':[hidden]'
            else:
                hide_next=True
        else:
            value=re.sub(r'(?i)((?:password|passwd|secret|token|api[-_]?key|authorization|credential)=)([^\s&;]+)',r'\1[hidden]',value)
        value=re.sub(r'(https?://)[^/\s:@]+:[^@\s/]+@',r'\1[hidden]@',value,flags=re.I)
        result.append(value)
    return result


def runtime_task(name, args, cwd):
    """Derive an identity, without treating arbitrary arguments as a file to run."""
    lower=name.lower()
    runtime='Python' if lower.startswith(('python','pypy')) else 'Node.js' if lower in ('node.exe','node') else None
    if not runtime:
        return dict(label=FRIENDLY.get(lower,name),task=None,script=None,runtime=None)
    index=1
    script=None
    task=None
    while index<len(args):
        arg=args[index]
        if runtime=='Python' and arg=='-m' and index+1<len(args):
            task='module '+args[index+1]
            break
        if arg in ('-c','--eval','-e','--print','-p'):
            task='inline command'
            break
        if arg in ('-W','-X','--require','-r','--loader','--import','--check-hash-based-pycs'):
            index+=2
            continue
        if arg.startswith('-'):
            index+=1
            continue
        if arg.endswith(('.py','.pyw','.pyz','.js','.cjs','.mjs','.ts')):
            task=Path(arg).name
            if cwd:
                script=os.path.abspath(os.path.join(cwd,arg))
            elif os.path.isabs(arg):
                script=arg
        break
    return dict(label=f'{runtime} · {task}' if task else runtime,task=task,script=script,runtime=runtime)


def close_reason(process, protected, owner, windows, monitor_pid):
    if process.pid==monitor_pid:
        return 'This is Pulse’s own monitoring service. Ending it would stop the dashboard and recording.'
    if process.pid in protected:
        return 'This process is an ancestor of Pulse. It may host the dashboard session.'
    if process.pid<=4:
        return 'This is a core Windows process.'
    try:
        if process.username()!=owner:
            return 'This process belongs to a different account or a Windows service account.'
        executable=Path(process.exe()).resolve()
        if windows==executable or windows in executable.parents:
            return 'This executable is inside the Windows system directory.'
    except (psutil.Error,OSError):
        return 'Windows does not grant Pulse enough access to safely manage this process.'
    return None


def checked_process(pid, created):
    pid=int(pid)
    created=float(created)
    if pid<=0 or not math.isfinite(created):
        raise ValueError('Invalid process identity')
    process=psutil.Process(pid)
    if process.create_time()!=created:
        raise ValueError('This PID now belongs to a different process. Refresh the list.')
    return process


def process_metadata(process, name, owner, windows, monitor_pid):
    denied=[]
    def read(field, method, default=None):
        try:
            return method()
        except (psutil.Error,OSError):
            denied.append(field)
            return default
    executable=read('executable',process.exe)
    username=read('owner',process.username)
    runtime=name.lower().startswith(('python','pypy')) or name.lower() in ('node.exe','node')
    args=read('command',process.cmdline,[]) if runtime else []
    cwd=read('workingFolder',process.cwd) if runtime else None
    identity=runtime_task(name,args,cwd)
    if process.pid==monitor_pid:
        identity.update(label='Pulse monitor',task='server.py')
    system=bool(executable and (windows==Path(executable) or windows in Path(executable).parents))
    group_key=(executable or name).lower()+'|'+(identity['script'] or identity['task'] or '')
    return dict(**identity, executable=executable, mine=username==owner, system=system,
                groupKey=group_key, inspectionLimited=bool(denied))


def inspect_process(process, reason):
    denied=[]
    def read(field, method, default=None):
        try:
            return method()
        except (psutil.Error,OSError,NotImplementedError):
            denied.append(field)
            return default
    created=process.create_time()
    name=read('name',process.name,'Unknown process')
    args=read('command',process.cmdline,[])
    cwd=read('workingFolder',process.cwd)
    identity=runtime_task(name,args,cwd)
    parent=read('parent',process.parent)
    parent_info=None
    if parent:
        try:
            # Parent PIDs can be reused after their original owner exits.
            parent_created=parent.create_time()
            if parent_created<=created:
                parent_info=dict(pid=parent.pid,name=parent.name(),created=parent_created)
        except (psutil.Error,OSError):
            denied.append('parent')
    children=[]
    for child in read('children',process.children,[])[:100]:
        try:
            children.append(dict(pid=child.pid,name=child.name(),created=child.create_time()))
        except (psutil.Error,OSError):
            pass
    memory=read('memory',process.memory_info)
    io=read('ioCounters',process.io_counters)
    command=redact_command(args)
    result=dict(pid=process.pid,created=created,name=name,**identity,
                executable=read('executable',process.exe),workingFolder=cwd,
                command=subprocess.list2cmdline(command) if command else None,
                commandRedacted=command!=args,owner=read('owner',process.username),
                status=read('status',process.status),threads=read('threads',process.num_threads),
                handles=read('handles',process.num_handles) if hasattr(process,'num_handles') else None,
                memory=memory.rss if memory else None, parent=parent_info,children=children,
                ioCounters=dict(read=io.read_bytes,write=io.write_bytes) if io else None,
                canClose=reason is None,protectionReason=reason,unavailable=denied)
    # Reject if the selected process exited during inspection.
    if not process.is_running() or process.create_time()!=created:
        raise psutil.NoSuchProcess(process.pid)
    return result
