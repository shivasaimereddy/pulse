import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import psutil
from pulse.process_tools import checked_process, close_reason, inspect_process, process_metadata, redact_command, runtime_task


def fake_process():
    process=Mock()
    process.pid=123
    process.create_time.return_value=1000.0
    process.name.return_value='python.exe'
    process.exe.return_value=r'C:\Apps\Python\python.exe'
    process.cmdline.return_value=['python.exe','-u','server.py','--token','sensitive']
    process.cwd.return_value=r'C:\Project'
    process.username.return_value='person'
    process.parent.return_value=None
    process.children.return_value=[]
    process.memory_info.return_value=Mock(rss=2048)
    process.io_counters.return_value=Mock(read_bytes=100,write_bytes=50)
    process.num_threads.return_value=4
    process.num_handles.return_value=20
    process.status.return_value='running'
    process.is_running.return_value=True
    return process


class ProcessTests(unittest.TestCase):
    def test_identifies_python_script_with_flags(self):
        identity=runtime_task('python.exe',['python','-X','utf8','-u','server.py'],r'C:\Project')
        self.assertEqual(identity['label'],'Python · server.py')
        self.assertEqual(identity['script'],os.path.abspath(r'C:\Project\server.py'))

    def test_module_and_inline_command_are_not_script_paths(self):
        module=runtime_task('python.exe',['python','-m','http.server'],r'C:\Project')
        inline=runtime_task('python.exe',['python','-c','print(1)'],r'C:\Project')
        self.assertEqual(module['task'],'module http.server')
        self.assertIsNone(module['script'])
        self.assertEqual(inline['task'],'inline command')
        self.assertIsNone(inline['script'])

    def test_distinct_scripts_have_distinct_group_keys(self):
        p=fake_process()
        a=process_metadata(p,'python.exe','person',Path(r'C:\Windows'),999)
        p.cwd.return_value=r'C:\OtherProject'
        b=process_metadata(p,'python.exe','person',Path(r'C:\Windows'),999)
        self.assertNotEqual(a['groupKey'],b['groupKey'])
        self.assertNotIn('sensitive',str(a))

    def test_common_secret_arguments_are_redacted(self):
        args=['app','--token','abc','--password=def','API_KEY=ghi','https://user:password@example.com/?token=jkl']
        result=redact_command(args)
        self.assertEqual(result[2],'[hidden]')
        self.assertEqual(result[3],'--password=[hidden]')
        self.assertEqual(result[4],'API_KEY=[hidden]')
        self.assertNotIn('user:password',result[5])
        self.assertNotIn('jkl',result[5])
        self.assertEqual(args[2],'abc')

    def test_reused_pid_is_rejected(self):
        p=fake_process()
        with patch('pulse.process_tools.psutil.Process',return_value=p):
            with self.assertRaises(ValueError):
                checked_process(123,999.0)
            self.assertIs(checked_process(123,1000.0),p)

    def test_invalid_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            checked_process(123,float('nan'))
        with self.assertRaises(ValueError):
            checked_process(-1,1000)

    def test_monitor_protection_explains_why(self):
        p=fake_process()
        reason=close_reason(p,{123},'person',Path(r'C:\Windows'),123)
        self.assertIn('own monitoring service',reason)
        p.username.assert_not_called()

    def test_other_account_protected(self):
        p=fake_process()
        reason=close_reason(p,set(),'someone else',Path(r'C:\Windows'),999)
        self.assertIn('different account',reason)

    def test_inspection_returns_identity_and_redacted_command(self):
        p=fake_process()
        result=inspect_process(p,'Protected for testing')
        self.assertEqual(result['threads'],4)
        self.assertEqual(result['ioCounters']['read'],100)
        self.assertFalse(result['canClose'])
        self.assertTrue(result['commandRedacted'])
        self.assertNotIn('sensitive',result['command'])

    def test_denied_fields_do_not_fail_entire_inspection(self):
        p=fake_process()
        p.exe.side_effect=psutil.AccessDenied(123)
        p.cmdline.side_effect=psutil.AccessDenied(123)
        result=inspect_process(p,'Access limited')
        self.assertIsNone(result['executable'])
        self.assertIsNone(result['command'])
        self.assertIn('command',result['unavailable'])

    def test_parent_pid_reuse_is_not_shown_as_parent(self):
        p=fake_process()
        parent=fake_process()
        parent.create_time.return_value=2000.0
        p.parent.return_value=parent
        self.assertIsNone(inspect_process(p,None)['parent'])

    def test_exit_during_inspection_is_reported(self):
        p=fake_process()
        p.is_running.return_value=False
        with self.assertRaises(psutil.NoSuchProcess):
            inspect_process(p,None)


if __name__=='__main__':
    unittest.main()
