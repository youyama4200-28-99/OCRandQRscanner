from __future__ import annotations

import logging
import os
import platform
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

LOGGER_NAME = "smartscan"
LOG_FILE_NAME = "smartscan.log"
_HANDLER_MARKER = "_smartscan_file_handler"
_ORIGINAL_SYS_HOOK = sys.excepthook
_ORIGINAL_THREAD_HOOK = getattr(threading, "excepthook", None)
_HOOKS_INSTALLED = False


def default_log_directory() -> Path:
    local_data = os.environ.get("LOCALAPPDATA")
    if local_data:
        return Path(local_data) / "SmartScan" / "logs"
    return Path.cwd() / "logs"


def configure_logging(
    log_directory: Path | None = None,
    level: str = "INFO",
    file_name: str = LOG_FILE_NAME,
) -> Path:
    directory = (log_directory or default_log_directory()).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / file_name

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    for handler in list(logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            logger.removeHandler(handler)
            handler.close()

    handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
        delay=True,
    )
    setattr(handler, _HANDLER_MARKER, True)
    handler.setLevel(logger.level)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s.%(msecs)03d %(levelname)-8s [%(threadName)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    _install_exception_hooks(logger)
    logger.info(
        "SmartScan starting; python=%s os=%s frozen=%s pid=%d log=%s",
        platform.python_version(),
        platform.platform(),
        bool(getattr(sys, "frozen", False)),
        os.getpid(),
        log_path,
    )
    return log_path


def close_logging() -> None:
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            logger.removeHandler(handler)
            handler.close()


def _install_exception_hooks(logger: logging.Logger) -> None:
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return

    def sys_hook(
        exception_type: type[BaseException],
        exception: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        logger.critical(
            "Unhandled exception on main thread",
            exc_info=(exception_type, exception, traceback),
        )
        _ORIGINAL_SYS_HOOK(exception_type, exception, traceback)

    sys.excepthook = sys_hook

    if _ORIGINAL_THREAD_HOOK is not None:

        def thread_hook(args: threading.ExceptHookArgs) -> None:
            logger.critical(
                "Unhandled exception on thread %s",
                args.thread.name if args.thread else "unknown",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
            _ORIGINAL_THREAD_HOOK(args)

        threading.excepthook = thread_hook
    _HOOKS_INSTALLED = True
