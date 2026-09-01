from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .app_logging import configure_logging
from .config import load_settings


def default_config_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "config" / "settings.json"
    return Path("config/settings.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automatic webcam QR and OCR scanner")
    parser.add_argument("--config", type=Path, default=default_config_path())
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--log-dir", type=Path, help="Directory for rotating application logs")
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        log_path = configure_logging(args.log_dir, args.log_level)
    except OSError as exc:
        print(f"Logging error: {exc}", file=sys.stderr)
        return 3
    logger = logging.getLogger("smartscan.main")
    logger.info("Arguments parsed; config=%s log_level=%s", args.config, args.log_level)
    if "PADDLE_PDX_CACHE_HOME" not in os.environ:
        local_data = os.environ.get("LOCALAPPDATA")
        cache_root = Path(local_data) / "SmartScan" if local_data else Path.cwd() / ".cache"
        os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache_root / "paddlex")
    try:
        settings = load_settings(args.config)
    except ValueError as exc:
        logger.exception("Settings could not be loaded from %s", args.config)
        print(f"Settings error: {exc}", file=sys.stderr)
        return 2
    logger.info(
        "Settings loaded; camera=%d resolution=%dx%d fps=%d device=%s",
        settings.camera.index,
        settings.camera.width,
        settings.camera.height,
        settings.camera.fps,
        settings.recognition.openvino_device,
    )
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
        window = MainWindow(settings, log_path=log_path, log_level=args.log_level)
        window.show()
        logger.info("Main window shown; entering Qt event loop")
        exit_code = application.exec()
        logger.info("Qt event loop exited; code=%d", exit_code)
        return exit_code
    except Exception as exc:
        logger.exception("Application startup failed")
        QMessageBox.critical(None, "SmartScan 起動エラー", f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
