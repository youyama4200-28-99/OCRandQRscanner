from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CameraSettings:
    index: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 30


@dataclass(frozen=True, slots=True)
class RecognitionSettings:
    language: str = "japan"
    minimum_confidence: float = 0.55
    ocr_interval_seconds: float = 3.0
    ocr_cpu_threads: int = 2
    qr_scan_interval_frames: int = 2
    qr_max_width: int = 640
    qr_hold_seconds: float = 1.0
    result_hold_seconds: float = 3.0
    text_score_threshold: float = 0.018
    openvino_device: str = "AUTO"
    gate_width: int = 320
    gate_height: int = 180


@dataclass(frozen=True, slots=True)
class UiSettings:
    window_title: str = "SmartScan - QR / OCR"
    mirror_preview: bool = False


@dataclass(frozen=True, slots=True)
class AppSettings:
    camera: CameraSettings = field(default_factory=CameraSettings)
    recognition: RecognitionSettings = field(default_factory=RecognitionSettings)
    ui: UiSettings = field(default_factory=UiSettings)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"'{name}' must be a JSON object")
    return value


def _only_known(cls: type[Any], values: dict[str, Any]) -> dict[str, Any]:
    allowed = cls.__dataclass_fields__.keys()
    unknown = set(values) - set(allowed)
    if unknown:
        raise ValueError(f"Unknown settings for {cls.__name__}: {', '.join(sorted(unknown))}")
    return values


def load_settings(path: Path | None = None) -> AppSettings:
    if path is None or not path.exists():
        settings = AppSettings()
    else:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not read settings '{path}': {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError("Settings root must be a JSON object")
        settings = AppSettings(
            camera=CameraSettings(**_only_known(CameraSettings, _section(raw, "camera"))),
            recognition=RecognitionSettings(
                **_only_known(RecognitionSettings, _section(raw, "recognition"))
            ),
            ui=UiSettings(**_only_known(UiSettings, _section(raw, "ui"))),
        )
    validate_settings(settings)
    return settings


def validate_settings(settings: AppSettings) -> None:
    camera = settings.camera
    recognition = settings.recognition
    if camera.index < 0:
        raise ValueError("camera.index must be 0 or greater")
    if min(camera.width, camera.height, camera.fps) <= 0:
        raise ValueError("camera width, height and fps must be positive")
    if not 0 <= recognition.minimum_confidence <= 1:
        raise ValueError("recognition.minimum_confidence must be between 0 and 1")
    if recognition.ocr_interval_seconds <= 0 or recognition.qr_hold_seconds < 0:
        raise ValueError("recognition intervals are invalid")
    if recognition.ocr_cpu_threads <= 0:
        raise ValueError("recognition.ocr_cpu_threads must be positive")
    if recognition.qr_scan_interval_frames <= 0:
        raise ValueError("recognition.qr_scan_interval_frames must be positive")
    if recognition.qr_max_width < 160:
        raise ValueError("recognition.qr_max_width must be at least 160")
    if recognition.text_score_threshold < 0:
        raise ValueError("recognition.text_score_threshold must be 0 or greater")
    if min(recognition.gate_width, recognition.gate_height) < 16:
        raise ValueError("OpenVINO gate dimensions must be at least 16")
