from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from ..models import RecognitionResult, RecognizedItem


def _as_mapping(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        payload: Any = result
    else:
        payload = getattr(result, "json", {})
        if callable(payload):
            payload = payload()
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("res", payload)
    return nested if isinstance(nested, dict) else {}


def _polygon(value: Any) -> tuple[tuple[int, int], ...]:
    if value is None:
        return ()
    try:
        return tuple((int(round(point[0])), int(round(point[1]))) for point in value)
    except (IndexError, TypeError, ValueError):
        return ()


def parse_predict_results(results: Iterable[Any], minimum_confidence: float) -> RecognitionResult:
    items: list[RecognizedItem] = []
    for result in results:
        data = _as_mapping(result)
        texts = data.get("rec_texts", [])
        scores = data.get("rec_scores", [])
        polygons = data.get("rec_polys", data.get("dt_polys", []))
        for index, text in enumerate(texts):
            confidence = float(scores[index]) if index < len(scores) else 0.0
            if str(text).strip() and confidence >= minimum_confidence:
                polygon = _polygon(polygons[index]) if index < len(polygons) else ()
                items.append(RecognizedItem(str(text).strip(), confidence, polygon))
    return RecognitionResult(tuple(items))


def parse_legacy_results(results: Any, minimum_confidence: float) -> RecognitionResult:
    items: list[RecognizedItem] = []
    for page in results if isinstance(results, list) else []:
        if not isinstance(page, list):
            continue
        for entry in page:
            try:
                polygon, (text, confidence) = entry
                confidence = float(confidence)
            except (TypeError, ValueError):
                continue
            if str(text).strip() and confidence >= minimum_confidence:
                items.append(RecognizedItem(str(text).strip(), confidence, _polygon(polygon)))
    return RecognitionResult(tuple(items))


class PaddleOcrEngine:
    """Lazy PaddleOCR adapter initialized inside the single OCR worker."""

    def __init__(self, *, language: str, minimum_confidence: float) -> None:
        self.language = language
        self.minimum_confidence = minimum_confidence
        self._ocr: Any | None = None

    def _initialize(self) -> None:
        if self._ocr is not None:
            return
        from paddleocr import PaddleOCR

        options = {
            "lang": self.language,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
            # PaddlePaddle 3.3.1 + PP-OCRv6 uses an unsupported oneDNN PIR
            # attribute on Windows CPU. The plain CPU path is reliable.
            "enable_mkldnn": False,
        }
        self._ocr = PaddleOCR(**options)

    def recognize(self, frame: Any) -> RecognitionResult:
        self._initialize()
        if hasattr(self._ocr, "predict"):
            return parse_predict_results(self._ocr.predict(frame), self.minimum_confidence)
        return parse_legacy_results(self._ocr.ocr(frame, cls=False), self.minimum_confidence)
