from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

Point = tuple[int, int]
Polygon = tuple[Point, ...]


class ScanMode(str, Enum):
    STARTING = "準備中"
    SEARCHING = "探索中"
    QR = "QR"
    OCR = "OCR"
    ERROR = "エラー"


@dataclass(frozen=True, slots=True)
class RecognizedItem:
    text: str
    confidence: float
    polygon: Polygon = ()


@dataclass(frozen=True, slots=True)
class RecognitionResult:
    items: tuple[RecognizedItem, ...] = ()

    @property
    def text(self) -> str:
        return "\n".join(item.text for item in self.items if item.text.strip())

    @property
    def average_confidence(self) -> float:
        if not self.items:
            return 0.0
        return sum(item.confidence for item in self.items) / len(self.items)
