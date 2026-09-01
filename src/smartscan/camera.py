from __future__ import annotations

import logging
import time
from typing import Any

import cv2

from .config import CameraSettings

logger = logging.getLogger("smartscan.camera")


class Camera:
    def __init__(self, settings: CameraSettings) -> None:
        self.settings = settings
        self._capture: Any | None = None
        self._read_failures = 0

    @property
    def is_open(self) -> bool:
        return bool(self._capture is not None and self._capture.isOpened())

    def open(self) -> bool:
        started_at = time.perf_counter()
        logger.info("Opening camera; index=%d backend=DSHOW", self.settings.index)
        self.close()
        capture = cv2.VideoCapture(self.settings.index, cv2.CAP_DSHOW)
        if not capture.isOpened():
            logger.warning("DirectShow camera open failed; retrying with default backend")
            capture.release()
            capture = cv2.VideoCapture(self.settings.index)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.height)
        capture.set(cv2.CAP_PROP_FPS, self.settings.fps)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._capture = capture
        opened = capture.isOpened()
        self._read_failures = 0
        logger.info(
            "Camera open completed; success=%s backend=%s actual=%dx%d fps=%.1f elapsed_ms=%.1f",
            opened,
            capture.getBackendName() if opened else "unavailable",
            round(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            capture.get(cv2.CAP_PROP_FPS),
            (time.perf_counter() - started_at) * 1000,
        )
        return opened

    def read(self) -> tuple[bool, Any]:
        if not self.is_open:
            return False, None
        ok, frame = self._capture.read()
        if ok:
            if self._read_failures:
                logger.info("Camera reads recovered after %d failures", self._read_failures)
            self._read_failures = 0
        else:
            self._read_failures += 1
            if self._read_failures == 1 or self._read_failures % 30 == 0:
                logger.warning("Camera read failed; consecutive_failures=%d", self._read_failures)
        return ok, frame

    def close(self) -> None:
        if self._capture is not None:
            logger.info("Closing camera")
            self._capture.release()
            self._capture = None
