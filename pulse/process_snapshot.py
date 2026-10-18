"""One bounded Windows system snapshot per sampling interval; psutil fallback.

Layout reference: System Informer's phnt SYSTEM_PROCESS_INFORMATION header:
https://github.com/winsiderss/systeminformer/blob/master/phnt/include/ntexapi.h
Only read-only counters are queried. No handles are opened to change a process.
"""
import ctypes
import os

import psutil

U32=ctypes.c_uint32
U64=ctypes.c_uint64
I64=ctypes.c_int64
PTR=ctypes.c_void_p
SIZE=ctypes.c_size_t
EPOCH_TICKS=116444736000000000


class UnicodeString(ctypes.Structure):
    _fields_=[('length',ctypes.c_uint16),('maximum',ctypes.c_uint16),('buffer',PTR)]


class ProcessHeader(ctypes.Structure):
    _fields_=[('next',U32),('threads',U32),('private_working_set',U64),
              ('hard_faults',U32),('thread_peak',U32),('cycles',U64),
              ('created',I64),('user',I64),('kernel',I64),('image',UnicodeString),
              ('priority',ctypes.c_int32),('pid',PTR),('parent',PTR),
              ('handles',U32),('session',U32),('key',SIZE),('peak_virtual',SIZE),
              ('virtual',SIZE),('faults',U32),('peak_working_set',SIZE),('working_set',SIZE)]


def parse_snapshot(buffer, length):
    if not 0<length<=ctypes.sizeof(buffer):
        raise ValueError('Invalid snapshot buffer length')
    base=ctypes.addressof(buffer)
    offset=0
    rows=[]
    header_size=ctypes.sizeof(ProcessHeader)
    while True:
        if offset+header_size>length:
            raise ValueError('Truncated Windows process snapshot')
        header=ProcessHeader.from_buffer(buffer,offset)
        pid=header.pid or 0
        if header.image.length:
            address=header.image.buffer or 0
            if header.image.length%2 or address<base or address+header.image.length>base+length:
                raise ValueError('Invalid process name buffer')
            name=ctypes.string_at(address,header.image.length).decode('utf-16-le',errors='replace')
        else:
            name='System' if pid==4 else 'Unknown'
        if pid:
            rows.append(dict(pid=pid,name=name,memory=int(header.working_set),
                             cpu_time=(header.user+header.kernel)/10000000,
                             created=(header.created-EPOCH_TICKS)/10000000,
                             birth=int(header.created)))
        if not header.next:
            break
        if header.next<header_size or offset+header.next>=length:
            raise ValueError('Invalid process record offset')
        offset+=header.next
    return rows


def windows_snapshot():
    if os.name!='nt' or ctypes.sizeof(PTR)!=8:
        raise OSError('Native snapshot requires 64-bit Windows Python')
    query=ctypes.WinDLL('ntdll').NtQuerySystemInformation
    query.argtypes=[U32,PTR,U32,ctypes.POINTER(U32)]
    query.restype=ctypes.c_int32
    size=262144
    for attempt in range(6):
        if size>64*1024*1024:
            break
        buffer=ctypes.create_string_buffer(size)
        needed=U32()
        status=query(5,buffer,size,ctypes.byref(needed))
        if status==0:
            return parse_snapshot(buffer,needed.value or size)
        if status & 0xffffffff not in (0xc0000004,0xc0000023):
            raise OSError(f'Windows process query failed: {status & 0xffffffff:08x}')
        size=max(size*2,needed.value+65536)
    raise OSError('Windows process snapshot exceeded its allocation limit')


def compatibility_snapshot():
    rows=[]
    for process in psutil.process_iter(['pid','name','memory_info','cpu_times']):
        try:
            if not process.pid:
                continue
            info=process.info
            created=process.create_time()
            rows.append(dict(pid=process.pid,name=info['name'] or 'Unknown',
                             memory=info['memory_info'].rss,
                             cpu_time=info['cpu_times'].user+info['cpu_times'].system,
                             created=created,birth=created))
        except (psutil.Error,OSError,AttributeError):
            pass
    return rows


class ProcessSnapshot:
    def __init__(self):
        self.native=os.name=='nt' and ctypes.sizeof(PTR)==8
        self.error=None

    def read(self):
        if self.native:
            try:
                return windows_snapshot()
            except (OSError,ValueError,AttributeError) as exc:
                self.error=str(exc)
                self.native=False
        return compatibility_snapshot()
