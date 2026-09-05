from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import patch

import cv2

from smartscan.camera import Camera, discover_camera_indices
from smartscan.config import CameraSettings


class FakeCapture:
    def __init__(self, index: int, opened_indices: set[int]) -> None:
        self.index = index
        self._opened = index in opened_indices
        self.released = False
        self.read_count = 0
        self.read_thread_names: list[str] = []

    def isOpened(self) -> bool:  # noqa: N802
        return self._opened and not self.released

    def release(self) -> None:
        self.released = True

    def set(self, _property: int, _value: float) -> bool:
        return True

    def read(self) -> tuple[bool, object]:
        time.sleep(0.005)
        self.read_count += 1
        self.read_thread_names.append(threading.current_thread().name)
        return True, _FakeFrame()

    def get(self, property_id: int) -> float:
        values = {
            cv2.CAP_PROP_FRAME_WIDTH: 1280,
            cv2.CAP_PROP_FRAME_HEIGHT: 720,
            cv2.CAP_PROP_FPS: 30,
        }
        return float(values.get(property_id, 0))

    def getBackendName(self) -> str:  # noqa: N802
        return "DSHOW"


class CameraTests(unittest.TestCase):
    def test_discovery_returns_open_indices_and_respects_exclusions(self) -> None:
        opened = {0, 2}
        captures: list[FakeCapture] = []

        def create_capture(index: int, _backend: int | None = None) -> FakeCapture:
            capture = FakeCapture(index, opened)
            captures.append(capture)
            return capture

        with patch("smartscan.camera.cv2.VideoCapture", side_effect=create_capture):
            result = discover_camera_indices(3, excluded_indices=frozenset({0}))

        self.assertEqual(result, (2,))
        self.assertTrue(all(capture.released for capture in captures))

    def test_open_can_switch_camera_index(self) -> None:
        with patch(
            "smartscan.camera.cv2.VideoCapture",
            side_effect=lambda index, *_args: FakeCapture(index, {0, 2}),
        ):
            camera = Camera(CameraSettings(index=0))
            self.assertTrue(camera.open(2))
            camera.close()

        self.assertEqual(camera.current_index, 2)

    def test_read_returns_latest_frame_without_calling_capture_on_ui_thread(self) -> None:
        capture = FakeCapture(0, {0})
        with patch("smartscan.camera.cv2.VideoCapture", return_value=capture):
            camera = Camera(CameraSettings(index=0))
            self.assertTrue(camera.open())
            deadline = time.monotonic() + 0.5
            ok = False
            while time.monotonic() < deadline:
                ok, _frame = camera.read()
                if ok:
                    break
                time.sleep(0.005)
            started_at = time.perf_counter()
            camera.read()
            elapsed = time.perf_counter() - started_at
            camera.close()

        self.assertTrue(ok)
        self.assertTrue(capture.read_thread_names)
        self.assertTrue(
            all(name.startswith("camera-capture-") for name in capture.read_thread_names)
        )
        self.assertLess(elapsed, 0.02)


class _FakeFrame:
    def copy(self) -> _FakeFrame:
        return self


if __name__ == "__main__":
    unittest.main()
