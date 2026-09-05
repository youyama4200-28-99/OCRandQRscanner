from __future__ import annotations

import logging
import time
from typing import Any

import cv2

from .config import CameraSettings

logger = logging.getLogger("smartscan.camera")


def discover_camera_indices(
    max_index: int, *, excluded_indices: frozenset[int] = frozenset()
) -> tuple[int, ...]:
    """Probe DirectShow camera indices without blocking the UI thread."""
    started_at = time.perf_counter()
    found: list[int] = []
    logger.info(
        "Camera discovery started; max_index=%d excluded=%s",
        max_index,
        sorted(excluded_indices),
    )
    for index in range(max_index + 1):
        if index in excluded_indices:
            continue
        capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            capture = cv2.VideoCapture(index)
        try:
            if capture.isOpened():
                found.append(index)
        finally:
            capture.release()
    logger.info(
        "Camera discovery completed; indices=%s elapsed_ms=%.1f",
        found,
        (time.perf_counter() - started_at) * 1000,
    )
    return tuple(found)


class Camera:
    def __init__(self, settings: CameraSettings) -> None:
        self.settings = settings
        self._index = settings.index
        self._capture: Any | None = None
        self._read_failures = 0

    @property
    def is_open(self) -> bool:
        return bool(self._capture is not None and self._capture.isOpened())

    @property
    def current_index(self) -> int:
        return self._index

    def open(self, index: int | None = None) -> bool:
        target_index = self._index if index is None else index
        started_at = time.perf_counter()
        logger.info("Opening camera; index=%d backend=DSHOW", target_index)
        self.close()
        capture = cv2.VideoCapture(target_index, cv2.CAP_DSHOW)
        if not capture.isOpened():
            logger.warning("DirectShow camera open failed; retrying with default backend")
            capture.release()
            capture = cv2.VideoCapture(target_index)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.height)
        capture.set(cv2.CAP_PROP_FPS, self.settings.fps)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._capture = capture
        opened = capture.isOpened()
        if opened:
            self._index = target_index
        self._read_failures = 0
        logger.info(
            "Camera open completed; index=%d success=%s backend=%s actual=%dx%d "
            "fps=%.1f elapsed_ms=%.1f",
            target_index,
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
