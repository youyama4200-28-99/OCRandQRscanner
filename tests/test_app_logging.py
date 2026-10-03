from __future__ import annotations

import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from smartscan.app_logging import close_logging, configure_logging, default_log_directory


class AppLoggingTests(unittest.TestCase):
    def test_default_log_directory_uses_local_app_data(self) -> None:
        with patch.dict(os.environ, {"LOCALAPPDATA": r"C:\LocalData"}):
            self.assertEqual(
                default_log_directory(),
                Path(r"C:\LocalData") / "SmartScan" / "logs",
            )

    def test_configure_logging_writes_utf8_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            try:
                log_path = configure_logging(Path(directory), "DEBUG")
                logging.getLogger("smartscan.test").info("日本語ログ")
                for handler in logging.getLogger("smartscan").handlers:
                    handler.flush()

                self.assertTrue(log_path.exists())
                self.assertIn("日本語ログ", log_path.read_text(encoding="utf-8"))
            finally:
                close_logging()


if __name__ == "__main__":
    unittest.main()
