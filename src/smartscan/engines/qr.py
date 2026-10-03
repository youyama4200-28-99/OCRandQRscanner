from __future__ import annotations

from typing import Any

import cv2

from ..models import RecognitionResult, RecognizedItem


class QrEngine:
    def __init__(self, *, max_width: int | None = None) -> None:
        self._detector = cv2.QRCodeDetector()
        self.max_width = max_width

    @staticmethod
    def _polygon(points: Any) -> tuple[tuple[int, int], ...]:
        if points is None:
            return ()
        return tuple((int(round(point[0])), int(round(point[1]))) for point in points)

    def recognize(self, frame: Any) -> RecognitionResult:
        sample = frame
        scale = 1.0
        if self.max_width and frame.shape[1] > self.max_width:
            scale = self.max_width / frame.shape[1]
            sample = cv2.resize(
                frame,
                (self.max_width, max(1, round(frame.shape[0] * scale))),
                interpolation=cv2.INTER_AREA,
            )
        try:
            text, points, _ = self._detector.detectAndDecode(sample)
            if not text:
                return RecognitionResult()
            polygon = points[0] if points is not None and len(points) == 1 else points
            scaled_polygon = tuple(
                (round(x / scale), round(y / scale)) for x, y in self._polygon(polygon)
            )
            return RecognitionResult((RecognizedItem(text, 1.0, scaled_polygon),))
        except cv2.error:
            return RecognitionResult()
