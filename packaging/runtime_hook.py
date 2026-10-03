"""Runtime preparation executed before SmartScan imports in a frozen app."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

# Windowed PyInstaller applications set these streams to None. Some AI
# dependencies write status messages unconditionally, so provide a safe sink.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115

if "PADDLE_PDX_CACHE_HOME" not in os.environ:
    local_data = os.environ.get("LOCALAPPDATA")
    cache_root = Path(local_data) if local_data else Path.home() / "AppData" / "Local"
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache_root / "SmartScan" / "paddlex")
