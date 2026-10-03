import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from smartscan.__main__ import default_config_path


class MainTests(unittest.TestCase):
    def test_frozen_config_is_next_to_executable(self) -> None:
        executable = str(Path("C:/Apps/SmartScan/SmartScan.exe"))
        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "executable", executable),
        ):
            self.assertEqual(
                default_config_path(),
                Path(executable).parent / "config" / "settings.json",
            )


if __name__ == "__main__":
    unittest.main()
