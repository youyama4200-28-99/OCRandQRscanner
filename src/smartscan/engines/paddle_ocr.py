from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..app_logging import configure_logging
from ..models import RecognitionResult, RecognizedItem

logger = logging.getLogger("smartscan.paddle_ocr")


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

    def __init__(self, *, language: str, minimum_confidence: float, cpu_threads: int = 2) -> None:
        self.language = language
        self.minimum_confidence = minimum_confidence
        self.cpu_threads = cpu_threads
        self._ocr: Any | None = None

    def _initialize(self) -> None:
        if self._ocr is not None:
            return
        started_at = time.perf_counter()
        logger.info("PaddleOCR initialization started; language=%s", self.language)
        from paddleocr import PaddleOCR

        options = {
            "lang": self.language,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
            # PaddlePaddle 3.3.1 + PP-OCRv6 uses an unsupported oneDNN PIR
            # attribute on Windows CPU. The plain CPU path is reliable.
            "enable_mkldnn": False,
            "cpu_threads": self.cpu_threads,
        }
        try:
            self._ocr = PaddleOCR(**options)
        except Exception:
            logger.exception("PaddleOCR initialization failed")
            raise
        logger.info(
            "PaddleOCR initialization completed; elapsed_ms=%.1f",
            (time.perf_counter() - started_at) * 1000,
        )

    def recognize(self, frame: Any) -> RecognitionResult:
        started_at = time.perf_counter()
        try:
            self._initialize()
            if hasattr(self._ocr, "predict"):
                result = parse_predict_results(self._ocr.predict(frame), self.minimum_confidence)
            else:
                result = parse_legacy_results(
                    self._ocr.ocr(frame, cls=False), self.minimum_confidence
                )
        except Exception:
            logger.exception("PaddleOCR recognition failed")
            raise
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        log = logger.warning if elapsed_ms >= 2000 else logger.info
        log(
            "PaddleOCR recognition completed; items=%d elapsed_ms=%.1f",
            len(result.items),
            elapsed_ms,
        )
        return result


_worker_engine: PaddleOcrEngine | None = None


def initialize_ocr_worker(
    language: str,
    minimum_confidence: float,
    cpu_threads: int,
    log_directory: str,
    log_level: str,
) -> None:
    """Initialize process-local OCR state without sharing the UI process GIL."""
    global _worker_engine
    thread_count = str(cpu_threads)
    os.environ["OMP_NUM_THREADS"] = thread_count
    os.environ["OPENBLAS_NUM_THREADS"] = thread_count
    os.environ["MKL_NUM_THREADS"] = thread_count
    configure_logging(Path(log_directory), log_level, "smartscan-ocr-worker.log")
    logger.info("OCR worker process started; cpu_threads=%d", cpu_threads)
    _worker_engine = PaddleOcrEngine(
        language=language,
        minimum_confidence=minimum_confidence,
        cpu_threads=cpu_threads,
    )


def recognize_in_worker(frame: Any) -> RecognitionResult:
    if _worker_engine is None:
        raise RuntimeError("OCR worker is not initialized")
    return _worker_engine.recognize(frame)
