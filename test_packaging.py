"""Headless checks for installed storage and login-startup paths."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import mr3_paths
import mr3_startup


class PackagingTests(unittest.TestCase):
    def test_source_keeps_existing_user_data(self):
        with patch.object(sys, 'frozen', False, create=True):
            self.assertEqual(mr3_paths.data_directory(), mr3_paths.RESOURCE_DIR)

    def test_installed_data_is_independent_of_install_and_cwd(self):
        with patch.object(sys, 'frozen', True, create=True), patch.dict(os.environ, {'LOCALAPPDATA': r'C:\Users\Example\AppData\Local'}):
            self.assertEqual(mr3_paths.data_directory(), Path(r'C:\Users\Example\AppData\Local\MR3Control'))

    def test_frozen_startup_quotes_executable_with_spaces(self):
        exe = r'C:\Users\Example\AppData\Local\Programs\MR3 Control\MR3 Control.exe'
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', exe):
            self.assertEqual(mr3_startup.startup_command(), subprocess.list2cmdline([exe]))
            self.assertNotIn('wscript', mr3_startup.startup_command())

    def test_source_startup_still_uses_vbs(self):
        with patch.object(sys, 'frozen', False, create=True):
            self.assertIn('MR3 Control.vbs', mr3_startup.startup_command())


if __name__ == '__main__':
    unittest.main()
