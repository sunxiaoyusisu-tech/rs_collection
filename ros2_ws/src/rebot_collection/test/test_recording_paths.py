import tempfile
import unittest
from pathlib import Path

from rebot_collection.keyboard_collection_node import _unique_timestamp_path


class RecordingPathTest(unittest.TestCase):
    def test_uses_timestamp_name_when_available(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            parent = Path(temporary_directory) / "2026-08-12"
            parent.mkdir()
            actual = _unique_timestamp_path(parent, "2026-08-12_14-23-08")
            self.assertEqual(actual, parent / "2026-08-12_14-23-08")

    def test_appends_counter_instead_of_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            parent = Path(temporary_directory) / "2026-08-12"
            parent.mkdir()
            (parent / "2026-08-12_14-23-08").mkdir()
            (parent / "2026-08-12_14-23-08_02").mkdir()
            actual = _unique_timestamp_path(parent, "2026-08-12_14-23-08")
            self.assertEqual(actual, parent / "2026-08-12_14-23-08_03")


if __name__ == "__main__":
    unittest.main()
