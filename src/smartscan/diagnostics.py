from __future__ import annotations

import importlib.metadata
import platform
import sys

import numpy as np

from .config import AppSettings
from .engines.openvino_gate import OpenVinoTextGate

PACKAGES = (
    "numpy",
    "opencv-contrib-python",
    "openvino",
    "paddleocr",
    "paddlepaddle",
    "PySide6",
)


def run_diagnostics(settings: AppSettings) -> int:
    print(f"Python: {sys.version.split()[0]} ({platform.architecture()[0]})")
    failed = False
    for package in PACKAGES:
        try:
            print(f"{package}: {importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:
            print(f"{package}: NOT INSTALLED")
            failed = True
    try:
        gate = OpenVinoTextGate(
            width=settings.recognition.gate_width,
            height=settings.recognition.gate_height,
            device=settings.recognition.openvino_device,
        )
        blank = np.zeros(
            (settings.recognition.gate_height, settings.recognition.gate_width, 3), np.uint8
        )
        score = gate.score(blank)
        print(f"OpenVINO available devices: {', '.join(gate.info.available_devices) or '(none)'}")
        print(f"OpenVINO execution devices: {', '.join(gate.info.execution_devices)}")
        print(f"OpenVINO gate self-test: OK (blank score={score:.6f})")
    except Exception as exc:
        print(f"OpenVINO gate self-test: FAILED ({type(exc).__name__}: {exc})")
        failed = True
    return 1 if failed else 0
