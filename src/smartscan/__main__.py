from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .config import load_settings


def default_config_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "config" / "settings.json"
    return Path("config/settings.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automatic webcam QR and OCR scanner")
    parser.add_argument("--config", type=Path, default=default_config_path())
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if "PADDLE_PDX_CACHE_HOME" not in os.environ:
        local_data = os.environ.get("LOCALAPPDATA")
        cache_root = Path(local_data) / "SmartScan" if local_data else Path.cwd() / ".cache"
        os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache_root / "paddlex")
    try:
        settings = load_settings(args.config)
    except ValueError as exc:
        print(f"Settings error: {exc}", file=sys.stderr)
        return 2
    if args.diagnose:
        from .diagnostics import run_diagnostics

        return run_diagnostics(settings)
    if args.smoke_test:
        from .diagnostics import run_packaging_smoke_test

        return run_packaging_smoke_test(settings)

    from PySide6.QtWidgets import QApplication, QMessageBox

    from .ui.main_window import MainWindow

    application = QApplication(sys.argv if argv is None else [sys.argv[0], *argv])
    application.setApplicationName("SmartScan")
    application.setStyle("Fusion")
    try:
        window = MainWindow(settings)
        window.show()
        return application.exec()
    except Exception as exc:
        QMessageBox.critical(None, "SmartScan 起動エラー", f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
