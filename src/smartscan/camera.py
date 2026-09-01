from __future__ import annotations

from typing import Any

import cv2

from .config import CameraSettings


class Camera:
    def __init__(self, settings: CameraSettings) -> None:
        self.settings = settings
        self._capture: Any | None = None

    @property
    def is_open(self) -> bool:
        return bool(self._capture is not None and self._capture.isOpened())

    def open(self) -> bool:
        self.close()
        capture = cv2.VideoCapture(self.settings.index, cv2.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            capture = cv2.VideoCapture(self.settings.index)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.height)
        capture.set(cv2.CAP_PROP_FPS, self.settings.fps)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._capture = capture
        return capture.isOpened()

    def read(self) -> tuple[bool, Any]:
        if not self.is_open:
            return False, None
        return self._capture.read()

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
