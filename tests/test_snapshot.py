import ctypes
import os
import unittest
from unittest.mock import patch

import psutil
from pulse.process_snapshot import EPOCH_TICKS, ProcessHeader, ProcessSnapshot, parse_snapshot, windows_snapshot


class SnapshotTests(unittest.TestCase):
    def fixture(self, name='python.exe'):
        encoded=name.encode('utf-16-le')
        size=ctypes.sizeof(ProcessHeader)
        buffer=ctypes.create_string_buffer(size+len(encoded))
        header=ProcessHeader.from_buffer(buffer)
        header.pid=123
        header.created=EPOCH_TICKS+1000*10000000
        header.user=5*10000000
        header.kernel=2*10000000
        header.working_set=4096
        header.image.length=len(encoded)
        header.image.maximum=len(encoded)
        header.image.buffer=ctypes.addressof(buffer)+size
        ctypes.memmove(header.image.buffer,encoded,len(encoded))
        return buffer,header

    def test_snapshot_decodes_unicode_and_counters(self):
        buffer,header=self.fixture('工具.exe')
        row=parse_snapshot(buffer,ctypes.sizeof(buffer))[0]
        self.assertEqual(row['name'],'工具.exe')
        self.assertEqual(row['cpu_time'],7)
        self.assertEqual(row['created'],1000)
        self.assertEqual(row['memory'],4096)

    def test_idle_is_excluded(self):
        buffer,header=self.fixture()
        header.pid=0
        self.assertEqual(parse_snapshot(buffer,ctypes.sizeof(buffer)),[])

    def test_invalid_name_pointer_rejected_before_read(self):
        buffer,header=self.fixture()
        header.image.buffer=1
        with self.assertRaises(ValueError):
            parse_snapshot(buffer,ctypes.sizeof(buffer))

    def test_invalid_next_offset_and_truncation_rejected(self):
        buffer,header=self.fixture()
        header.next=1
        with self.assertRaises(ValueError):
            parse_snapshot(buffer,ctypes.sizeof(buffer))
        header.next=0
        with self.assertRaises(ValueError):
            parse_snapshot(buffer,ctypes.sizeof(ProcessHeader)-1)

    def test_oversized_buffer_length_rejected(self):
        buffer,header=self.fixture()
        with self.assertRaises(ValueError):
            parse_snapshot(buffer,ctypes.sizeof(buffer)+1)

    def test_native_failure_switches_to_compatibility(self):
        reader=ProcessSnapshot()
        reader.native=True
        with patch('pulse.process_snapshot.windows_snapshot',side_effect=OSError('unavailable')) as native, \
             patch('pulse.process_snapshot.compatibility_snapshot',return_value=[{'pid':1}]):
            self.assertEqual(reader.read(),[{'pid':1}])
            self.assertEqual(reader.read(),[{'pid':1}])
        native.assert_called_once()
        self.assertFalse(reader.native)

    @unittest.skipUnless(os.name=='nt' and ctypes.sizeof(ctypes.c_void_p)==8,'64-bit Windows only')
    def test_real_snapshot_matches_current_process_identity(self):
        process=psutil.Process()
        row=next(row for row in windows_snapshot() if row['pid']==process.pid)
        # FILETIME conversions can differ by one double-precision ULP.
        # The collector retains psutil's exact value for subsequent action checks.
        self.assertLess(abs(row['created']-process.create_time()),0.000001)
        self.assertGreater(row['memory'],0)
        self.assertEqual(row['name'].lower(),process.name().lower())


if __name__=='__main__':
    unittest.main()
