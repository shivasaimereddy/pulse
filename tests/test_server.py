import json
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import Mock, patch

import psutil
from pulse import server


class ActionTests(unittest.TestCase):
    def test_database_chooser_returns_path_or_cancel_without_switching(self):
        for selected in (None, 'C:/Selected/pulse.sqlite3'):
            with patch.object(server, 'choose_database', return_value=selected), patch.object(server, 'store') as workspace:
                request = urllib.request.Request(self.base + '/api/database/choose', data=b'{}',
                    headers={'X-Pulse-Token': server.ACTION_TOKEN, 'Origin': self.base, 'Content-Type': 'application/json'})
                with urllib.request.urlopen(request, timeout=5) as response:
                    self.assertEqual(json.load(response)['path'], selected)
                workspace.switch.assert_not_called()

    def test_database_actions_require_token_and_confirmation(self):
        with patch.object(server, 'store') as workspace, patch.object(server, 'choose_database') as picker:
            self.assertEqual(self.post({}, token='wrong', path='/api/database/choose'), 403)
            picker.assert_not_called()
            self.assertEqual(self.post({'path': 'C:/Example/pulse.sqlite3'}, path='/api/database/switch'), 400)
            workspace.switch.assert_not_called()

    def test_database_switch_is_blocked_during_scan(self):
        with patch.object(server, 'store') as workspace, patch.dict(server.scan, running=True):
            self.assertEqual(self.post({'path': 'C:/Example/pulse.sqlite3', 'confirm': True}, path='/api/database/switch'), 400)
            workspace.switch.assert_not_called()

    def test_database_switch_replaces_saved_scan_state(self):
        before = dict(server.scan)
        try:
            with patch.object(server, 'store') as workspace, patch.dict(server.scan, running=False):
                workspace.switch.return_value = {'path': 'C:/New', 'items': [], 'files': [], 'updated': 123}
                self.assertEqual(self.post({'path': 'C:/Example/pulse.sqlite3', 'confirm': True}, path='/api/database/switch'), 202)
                workspace.switch.assert_called_once_with('C:/Example/pulse.sqlite3')
                self.assertEqual(server.scan['path'], 'C:/New')
                self.assertFalse(server.scan['running'])
        finally:
            server.scan.clear()
            server.scan.update(before)

    def test_settings_mutations_require_a_session_token(self):
        with patch.object(server, 'store') as recording:
            self.assertEqual(self.post({'recordingEnabled': False}, token='wrong', path='/api/settings'), 403)
            recording.set_recording.assert_not_called()

    def test_settings_recording_change_is_explicit(self):
        with patch.object(server, 'store') as recording:
            self.assertEqual(self.post({'recordingEnabled': False}, path='/api/settings'), 202)
            recording.set_recording.assert_called_once_with(False)
            self.assertEqual(self.post({'unknown': True}, path='/api/settings'), 400)

    def test_performance_clear_requires_explicit_confirmation(self):
        with patch.object(server, 'store') as recording:
            self.assertEqual(self.post({}, path='/api/history/clear'), 400)
            recording.clear_performance.assert_not_called()
            self.assertEqual(self.post({'confirm': True}, path='/api/history/clear'), 202)
            recording.clear_performance.assert_called_once_with()

    def test_activity_endpoint_is_read_only_and_uncached(self):
        recording = Mock()
        recording.activity_timeline.return_value = dict(events=[], period='24h')
        with patch.object(server, 'store', recording):
            with urllib.request.urlopen(self.base + '/api/activity?range=24h', timeout=5) as response:
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                self.assertEqual(json.load(response)['events'], [])
            recording.activity_timeline.assert_called_once_with('24h')

    def test_expired_activity_comparison_returns_not_found(self):
        recording = Mock()
        recording.activity_comparison.return_value = None
        with patch.object(server, 'store', recording):
            with self.assertRaises(urllib.error.HTTPError) as result:
                urllib.request.urlopen(self.base + '/api/activity/comparison?id=1', timeout=5)
            self.assertEqual(result.exception.code, 404)

    def test_activity_comparison_rejects_invalid_identity(self):
        with patch.object(server, 'store', Mock()):
            with self.assertRaises(urllib.error.HTTPError) as result:
                urllib.request.urlopen(self.base + '/api/activity/comparison?id=999999999999999999999999', timeout=5)
            self.assertEqual(result.exception.code, 400)

    @classmethod
    def setUpClass(cls):
        cls.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.base = 'http://127.0.0.1:' + str(cls.http.server_port)
        threading.Thread(target=cls.http.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()

    def post(self, payload, token=server.ACTION_TOKEN, origin=None, path='/api/action'):
        request = urllib.request.Request(self.base + path, data=json.dumps(payload).encode(), headers={'X-Pulse-Token': token, 'Origin': origin or self.base, 'Content-Type': 'application/json'})
        try:
            return urllib.request.urlopen(request, timeout=5).status
        except urllib.error.HTTPError as error:
            return error.code

    def test_about_returns_version_and_local_installation_details(self):
        with urllib.request.urlopen(self.base + '/api/about', timeout=5) as response:
            payload = json.load(response)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(payload['version'], server.__version__)
        self.assertEqual(payload['name'], 'Pulse')
        self.assertEqual(payload['database'], str(server.ROOT / 'data' / 'pulse.sqlite3'))
        self.assertTrue(payload['python'])
        self.assertNotIn('token', payload)

    def test_clear_scan_history_requires_token(self):
        with patch.object(server,'store') as store:
            self.assertEqual(self.post({},token='wrong',path='/api/storage/clear-history'),403)
            store.clear_scans.assert_not_called()

    def test_clear_scan_history_rejects_running_scan(self):
        with patch.dict(server.scan, running=True), patch.object(server,'store') as store:
            self.assertEqual(self.post({},path='/api/storage/clear-history'),400)
            store.clear_scans.assert_not_called()

    def test_clear_scan_history_resets_live_snapshot(self):
        original=dict(server.scan)
        try:
            with patch.object(server,'store') as store:
                server.scan.update(running=False,updated=123,items=[{'name':'old'}])
                self.assertEqual(self.post({},path='/api/storage/clear-history'),202)
                store.clear_scans.assert_called_once_with()
                self.assertIsNone(server.scan['updated'])
                self.assertEqual(server.scan['items'],[])
        finally:
            server.scan.clear()
            server.scan.update(original)

    def test_action_requires_token(self):
        self.assertEqual(self.post({'action': 'settings', 'target': 'storage'}, token='wrong'), 403)

    def test_cross_origin_blocked(self):
        self.assertEqual(self.post({'action': 'settings', 'target': 'storage'}, origin='https://example.com'), 403)

    def test_settings_allowlist(self):
        with patch('pulse.server.os.startfile') as launch:
            self.assertEqual(self.post({'action': 'settings', 'target': 'storage'}), 200)
            launch.assert_called_once_with('ms-settings:storagesense')
            self.assertEqual(self.post({'action': 'settings', 'target': 'unknown'}), 400)
            self.assertEqual(launch.call_count, 1)

    def test_network_folder_blocked(self):
        with patch('pulse.server.subprocess.Popen') as launch:
            self.assertEqual(self.post({'action': 'folder', 'path': r'\\untrusted-server\share'}), 400)
            launch.assert_not_called()

    def test_reused_pid_blocked(self):
        process = Mock()
        process.create_time.return_value = 123
        with patch('pulse.server.psutil.Process', return_value=process):
            self.assertEqual(self.post({'action': 'close', 'pid': 12345, 'created': 100}), 400)
        process.terminate.assert_not_called()

    def test_protected_process_blocked(self):
        process = Mock()
        process.create_time.return_value = 123
        with patch('pulse.server.psutil.Process', return_value=process), patch('pulse.server.can_close', return_value=False):
            self.assertEqual(self.post({'action': 'close', 'pid': 12345, 'created': 123}), 400)
        process.terminate.assert_not_called()

    def test_eligible_process_termination(self):
        process = Mock()
        process.create_time.return_value = 123
        with patch('pulse.server.psutil.Process', return_value=process), patch('pulse.server.can_close', return_value=True):
            self.assertEqual(self.post({'action': 'close', 'pid': 12345, 'created': 123}), 200)
        process.terminate.assert_called_once()

    def test_monitor_is_protected(self):
        self.assertFalse(server.can_close(psutil.Process()))

    def test_process_folder_rejects_reused_pid(self):
        process=Mock()
        process.create_time.return_value=123
        with patch('pulse.process_tools.psutil.Process',return_value=process), patch('pulse.server.subprocess.Popen') as launch:
            self.assertEqual(self.post({'action':'process-folder','pid':12345,'created':100,'target':'working'}),400)
            launch.assert_not_called()

    def test_task_manager_uses_fixed_windows_path(self):
        with patch('pulse.server.subprocess.Popen') as launch:
            self.assertEqual(self.post({'action':'task-manager'}),200)
            launch.assert_called_once_with([str(server.WINDOWS_DIRECTORY/'System32'/'Taskmgr.exe')])

    def test_process_inspection_requires_session_token(self):
        request=urllib.request.Request(self.base+'/api/process?pid=123&created=1000')
        with self.assertRaises(urllib.error.HTTPError) as result:
            urllib.request.urlopen(request,timeout=5)
        self.assertEqual(result.exception.code,403)


if __name__ == '__main__':
    unittest.main()
