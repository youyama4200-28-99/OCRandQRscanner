import json
import tempfile
import unittest
from pathlib import Path

from smartscan.config import AppSettings, load_settings


class ConfigTests(unittest.TestCase):
    def test_defaults_when_file_is_missing(self) -> None:
        self.assertEqual(load_settings(Path("missing-settings.json")), AppSettings())

    def test_partial_settings_keep_section_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps({"camera": {"index": 2}}), encoding="utf-8")
            settings = load_settings(path)
        self.assertEqual(settings.camera.index, 2)
        self.assertEqual(settings.camera.width, 1280)
        self.assertEqual(settings.recognition.ocr_cpu_threads, 2)

    def test_unknown_setting_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps({"camera": {"unknown": 1}}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unknown settings"):
                load_settings(path)


if __name__ == "__main__":
    unittest.main()
