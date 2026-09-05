from __future__ import annotations

import logging
import threading
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
        self._capture_thread: threading.Thread | None = None
        self._capture_stop: threading.Event | None = None
        self._frame_lock = threading.Lock()
        self._latest_frame: Any | None = None
        self._latest_sequence = 0
        self._last_read_sequence = 0
        self._generation = 0
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
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
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
        if opened:
            self._generation += 1
            stop_event = threading.Event()
            self._capture_stop = stop_event
            self._capture_thread = threading.Thread(
                target=self._capture_loop,
                args=(capture, stop_event, target_index, self._generation),
                name=f"camera-capture-{target_index}",
                daemon=True,
            )
            self._capture_thread.start()
        return opened

    def read(self) -> tuple[bool, Any]:
        if not self.is_open:
            return False, None
        with self._frame_lock:
            if self._latest_frame is None or self._latest_sequence == self._last_read_sequence:
                return False, None
            frame = self._latest_frame.copy()
            self._last_read_sequence = self._latest_sequence
        return True, frame

    def _capture_loop(
        self,
        capture: Any,
        stop_event: threading.Event,
        camera_index: int,
        generation: int,
    ) -> None:
        window_started_at = time.perf_counter()
        window_frames = 0
        logger.info("Camera capture thread started; index=%d", camera_index)
        while not stop_event.is_set():
            read_started_at = time.perf_counter()
            try:
                ok, frame = capture.read()
            except Exception:
                if not stop_event.is_set():
                    logger.exception("Camera capture read raised; index=%d", camera_index)
                break
            read_elapsed = time.perf_counter() - read_started_at
            if stop_event.is_set():
                break
            if ok:
                if self._read_failures:
                    logger.info(
                        "Camera reads recovered; index=%d failures=%d",
                        camera_index,
                        self._read_failures,
                    )
                self._read_failures = 0
                with self._frame_lock:
                    if generation != self._generation:
                        break
                    self._latest_frame = frame
                    self._latest_sequence += 1
                window_frames += 1
            else:
                self._read_failures += 1
                if self._read_failures == 1 or self._read_failures % 30 == 0:
                    logger.warning(
                        "Camera read failed; index=%d consecutive_failures=%d",
                        camera_index,
                        self._read_failures,
                    )
                stop_event.wait(0.01)

            elapsed = time.perf_counter() - window_started_at
            if elapsed >= 5.0:
                logger.info(
                    "Camera capture rate; index=%d fps=%.1f frames=%d last_read_ms=%.1f",
                    camera_index,
                    window_frames / elapsed,
                    window_frames,
                    read_elapsed * 1000,
                )
                window_started_at = time.perf_counter()
                window_frames = 0
        logger.info("Camera capture thread stopped; index=%d", camera_index)

    def close(self) -> None:
        capture = self._capture
        if capture is None:
            return
        logger.info("Closing camera; index=%d", self._index)
        stop_event = self._capture_stop
        capture_thread = self._capture_thread
        if stop_event is not None:
            stop_event.set()
        if capture_thread is not None:
            capture_thread.join(timeout=1.25)
        if capture_thread is not None and capture_thread.is_alive():
            logger.warning("Camera read did not stop promptly; forcing release")
            capture.release()
            capture_thread.join(timeout=0.5)
        else:
            capture.release()
        self._capture = None
        self._capture_thread = None
        self._capture_stop = None
        with self._frame_lock:
            self._latest_frame = None
            self._latest_sequence = 0
            self._last_read_sequence = 0
