from __future__ import annotations

from typing import Any

import cv2

from ..models import RecognitionResult, RecognizedItem


class QrEngine:
    def __init__(self) -> None:
        self._detector = cv2.QRCodeDetector()

    @staticmethod
    def _polygon(points: Any) -> tuple[tuple[int, int], ...]:
        if points is None:
            return ()
        return tuple((int(round(point[0])), int(round(point[1]))) for point in points)

    def recognize(self, frame: Any) -> RecognitionResult:
        items: list[RecognizedItem] = []
        try:
            ok, decoded, points, _ = self._detector.detectAndDecodeMulti(frame)
            if ok and points is not None:
                for text, polygon in zip(decoded, points, strict=False):
                    if text:
                        items.append(RecognizedItem(text, 1.0, self._polygon(polygon)))
        except (cv2.error, ValueError):
            pass

        if not items:
            try:
                text, points, _ = self._detector.detectAndDecode(frame)
                if text:
                    polygon = points[0] if points is not None and len(points) == 1 else points
                    items.append(RecognizedItem(text, 1.0, self._polygon(polygon)))
            except cv2.error:
                return RecognitionResult()
        return RecognitionResult(tuple(items))
