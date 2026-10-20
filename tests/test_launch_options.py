import os
import unittest
from pathlib import Path
from unittest.mock import patch

from pulse.launch_options import database_option, appdata_database


class LaunchOptionsTests(unittest.TestCase):
    def test_default_preserves_existing_behavior(self):
        self.assertIsNone(database_option([]))

    def test_appdata_matches_executable_location(self):
        with patch.dict(os.environ, {'LOCALAPPDATA': str(Path.cwd() / 'example-appdata')}):
            self.assertEqual(database_option(['--appdata']), appdata_database().resolve())

    def test_explicit_path_expands_environment(self):
        with patch.dict(os.environ, {'PULSE_TEST_FOLDER': str(Path.cwd())}):
            self.assertEqual(database_option(['--database', '%PULSE_TEST_FOLDER%/existing.sqlite3']), (Path.cwd() / 'existing.sqlite3').resolve())

    @patch('pulse.launch_options.choose_database', return_value='')
    def test_cancel_does_not_fall_back_to_another_database(self, picker):
        self.assertIs(database_option(['--choose-database']), False)

    @patch('pulse.launch_options.choose_database', return_value='chosen.sqlite3')
    def test_picker_uses_selected_database(self, picker):
        self.assertEqual(database_option(['--choose-database']), (Path.cwd() / 'chosen.sqlite3').resolve())

    def test_conflicting_options_are_rejected(self):
        with patch('sys.stderr'), self.assertRaises(SystemExit):
            database_option(['--appdata', '--database', 'another.sqlite3'])

    @patch('pulse.launch_options.choose_database', return_value='')
    def test_cancel_never_starts_storage(self, picker):
        from pulse import server
        with patch.object(server, 'create_service') as create:
            server.main(['--choose-database'])
            create.assert_not_called()

    def test_busy_port_explains_how_to_switch(self):
        from pulse import server
        error = OSError('Address in use')
        error.winerror = 10048
        with patch.object(server, 'create_service', side_effect=error):
            with self.assertRaisesRegex(SystemExit, 'Quit it before'):
                server.main(['--appdata'])
