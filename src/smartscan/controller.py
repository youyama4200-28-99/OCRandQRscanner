from __future__ import annotations

from dataclasses import dataclass

from .models import ScanMode


@dataclass(frozen=True, slots=True)
class ScanDecision:
    mode: ScanMode
    run_ocr: bool


class AutoSwitchPolicy:
    """QR-first switching policy with hysteresis and OCR throttling."""

    def __init__(
        self, *, text_score_threshold: float, qr_hold_seconds: float, ocr_interval_seconds: float
    ) -> None:
        self.text_score_threshold = text_score_threshold
        self.qr_hold_seconds = qr_hold_seconds
        self.ocr_interval_seconds = ocr_interval_seconds
        self._qr_until = 0.0
        self._last_ocr_started = float("-inf")

    def decide(
        self, *, now: float, qr_found: bool, text_score: float, ocr_busy: bool
    ) -> ScanDecision:
        if qr_found:
            self._qr_until = now + self.qr_hold_seconds
            return ScanDecision(ScanMode.QR, False)
        if now < self._qr_until:
            return ScanDecision(ScanMode.QR, False)
        if text_score >= self.text_score_threshold:
            due = now - self._last_ocr_started >= self.ocr_interval_seconds
            run_ocr = due and not ocr_busy
            if run_ocr:
                self._last_ocr_started = now
            return ScanDecision(ScanMode.OCR, run_ocr)
        return ScanDecision(ScanMode.SEARCHING, False)
