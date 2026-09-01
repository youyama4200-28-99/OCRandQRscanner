"""PyInstaller entry point for the SmartScan Windows executable."""

from __future__ import annotations

import multiprocessing

from smartscan.__main__ import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
