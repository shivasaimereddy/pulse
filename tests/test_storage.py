import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pulse.history_store import HistoryStore
from pulse.storage_tools import FolderScanner, WslStorage, allowed_path, decode_output, parse_df

DF = '''Filesystem Type 1-blocks Used Available Capacity Mounted on
/dev/sdd ext4 1000 200 750 22% /
C:\\ 9p 500 300 200 60% /mnt/c
none tmpfs 500 10 490 2% /mnt/wslg
/dev/sdd ext4 1000 200 750 22% /mnt/shared
/dev/sde ext4 200 100 90 53% /mnt/data
/dev/sdb ext4 100 100 0 100% /usr/lib/linux-tools
'''


class StorageTests(unittest.TestCase):
    def test_mounts_separate_windows_and_shared_filesystems(self):
        rows = parse_df(DF)
        self.assertEqual([r['path'] for r in rows], ['/', '/mnt/c', '/mnt/shared', '/mnt/data'])
        self.assertTrue(rows[1]['windows'])
        self.assertTrue(rows[2]['shared'])
        self.assertFalse(rows[3]['shared'])
        self.assertEqual(rows[0]['used'],200)

    def test_wsl_output_decoding(self):
        self.assertEqual(decode_output('Ubuntu-24.04\r\n'.encode('utf-16-le')), 'Ubuntu-24.04')
        self.assertEqual(decode_output(DF.encode()), DF.strip())

    def test_no_probe_command_for_stopped_distribution(self):
        distros=[dict(name='Ubuntu',version=2,disk=None),dict(name='Docker',version=2,disk=None)]
        probe=WslStorage()
        with patch('pulse.storage_tools.registered_distros',return_value=distros), \
             patch('pulse.storage_tools.run_wsl',side_effect=[(0,'Ubuntu',''),(0,DF,'')]) as command, \
             patch('pulse.storage_tools.virtual_disk',side_effect=FileNotFoundError):
            probe.inspect()
        self.assertEqual(command.call_count,2)
        self.assertEqual(command.call_args_list[1].args[0][1],'Ubuntu')
        self.assertFalse(probe.state['distros'][1]['running'])
        self.assertEqual(probe.state['distros'][1]['mounts'],[])

    def test_linux_scan_rejects_stopped_distro_and_arbitrary_path(self):
        probe=WslStorage()
        with patch('pulse.storage_tools.run_wsl',return_value=(0,'Ubuntu','')) as command:
            with self.assertRaises(ValueError):
                probe.start_scan('Stopped','/home')
            self.assertEqual(command.call_count,1)
            with self.assertRaises(ValueError):
                probe.start_scan('Ubuntu','/mnt/c')
            self.assertEqual(command.call_count,1)

    def test_linux_scan_parses_partial_readable_results(self):
        probe=WslStorage()
        with patch('pulse.storage_tools.run_wsl',return_value=(1,'20\t/home/user\n30\t/home\n','Permission denied')):
            probe.scan('Ubuntu','/home')
        self.assertEqual(probe.state['scan']['items'][0]['size'],30)
        self.assertIn('incomplete',probe.state['scan']['error'])

    def test_network_paths_rejected_before_resolution(self):
        with self.assertRaises(ValueError):
            allowed_path(r'\\server\share')

    def test_folder_scan_sizes_and_bounded_largest_files(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            (root/'nested').mkdir()
            for number in range(60):
                (root/'nested'/f'{number}.dat').write_bytes(b'x'*number)
            (root/'single.txt').write_bytes(b'abc')
            save=Mock()
            scanner=FolderScanner(threading.Lock(),save)
            scanner.state['path']=str(root)
            scanner.run(root)
            state=scanner.state
            self.assertEqual(state['visited'],61)
            self.assertEqual(sum(row['size'] for row in state['items']),sum(range(60))+3)
            self.assertEqual(len(state['files']),50)
            self.assertEqual(state['files'][0]['size'],59)
            self.assertFalse(state['running'])
            save.assert_called_once()

    def test_single_scan_records_nested_folders_and_subtree_largest_files(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            (root/'one'/'two').mkdir(parents=True)
            (root/'one'/'small.txt').write_bytes(b'abc')
            (root/'one'/'two'/'large.txt').write_bytes(b'x'*20)
            (root/'other.txt').write_bytes(b'x'*40)
            store=HistoryStore(root/'history.sqlite3')
            scanner=FolderScanner(threading.Lock(),store.save_scan)
            scanner.run(root)
            state=store.latest_scan()
            self.assertEqual(state['size'],sum(item['size'] for item in state['items']))
            one=store.browse_scan(str(root),str(root/'one'))
            two=store.browse_scan(str(root),str(root/'one'/'two'))
            self.assertEqual(one['size'],23)
            self.assertEqual(two['size'],20)
            self.assertEqual(one['files'][0]['name'],'large.txt')
            self.assertEqual(one['visited'],2)
            self.assertEqual(state['indexVersion'],2)
            self.assertNotIn('indexPath',state)
            self.assertNotIn('tree',state)
            self.assertFalse(state['treeLimited'])

    def test_cancelled_scan_does_not_replace_saved_scan(self):
        with tempfile.TemporaryDirectory() as root:
            save=Mock()
            scanner=FolderScanner(threading.Lock(),save)
            scanner.cancel.set()
            scanner.run(Path(root))
            self.assertTrue(scanner.state['cancelled'])
            save.assert_not_called()

    def test_index_persistence_failure_is_visible_and_staging_is_removed(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            (root/'file').write_bytes(b'abc')
            staging=[]
            def fail(data):
                staging.append(data['indexPath'])
                self.assertTrue(Path(staging[0]).exists())
                raise OSError('disk full')
            scanner=FolderScanner(threading.Lock(),fail)
            scanner.run(root)
            self.assertFalse(scanner.state['running'])
            self.assertIn('disk full',scanner.state['failure'])
            self.assertFalse(Path(staging[0]).exists())

    def test_immediate_children_are_bounded_to_largest_500(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            for number in range(505):
                (root/f'{number}.dat').write_bytes(b'x'*number)
            scanner=FolderScanner(threading.Lock(),Mock())
            scanner.run(root)
            self.assertEqual(scanner.state['totalItems'],505)
            self.assertEqual(len(scanner.state['items']),500)
            self.assertEqual(scanner.state['items'][-1]['size'],5)


if __name__=='__main__':
    unittest.main()
