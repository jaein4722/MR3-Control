"""Headless release metadata validation."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('prepare_version', Path(__file__).parent / 'packaging/prepare_version.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_accepts_matching_stable_tag(self):
        self.assertEqual(release.validate_version('1.20.3', 'v1.20.3'), '1.20.3')

    def test_rejects_mismatched_tag(self):
        with self.assertRaises(ValueError):
            release.validate_version('0.1.2', 'v0.1.1')

    def test_rejects_invalid_windows_versions(self):
        for value in ('01.2.3', '1.2', '1.2.3-rc1', '1.2.3\n', '1.2.65536', '1.2.3/../x'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                release.validate_version(value)


if __name__ == '__main__':
    unittest.main()
