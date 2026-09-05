from __future__ import annotations

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

    def isOpened(self) -> bool:  # noqa: N802
        return self._opened and not self.released

    def release(self) -> None:
        self.released = True

    def set(self, _property: int, _value: float) -> bool:
        return True

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

        self.assertEqual(camera.current_index, 2)


if __name__ == "__main__":
    unittest.main()
