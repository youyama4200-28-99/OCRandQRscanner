from __future__ import annotations

import importlib.metadata
import multiprocessing
import os
import platform
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

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


def run_packaging_smoke_test(settings: AppSettings) -> int:
    """Exercise dynamic AI imports and inference paths in a frozen executable."""
    messages: list[str] = []
    exit_code = 0
    try:
        import cv2
        import paddle
        import paddleocr
        import paddlex
        from PySide6.QtCore import qVersion

        from .engines.paddle_ocr import initialize_ocr_worker, recognize_in_worker
        from .engines.qr import QrEngine

        messages.append(
            "imports: OK "
            f"(cv2={cv2.__version__}, paddle={paddle.__version__}, "
            f"paddleocr={paddleocr.__version__}, paddlex={paddlex.__version__}, "
            f"Qt={qVersion()})"
        )

        gate = OpenVinoTextGate(
            width=settings.recognition.gate_width,
            height=settings.recognition.gate_height,
            device=settings.recognition.openvino_device,
        )
        blank = np.zeros((180, 640, 3), dtype=np.uint8)
        text_image = blank.copy()
        cv2.putText(
            text_image,
            "SMARTSCAN 123",
            (20, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.8,
            (255, 255, 255),
            4,
            cv2.LINE_AA,
        )
        if gate.score(text_image) <= gate.score(blank):
            raise RuntimeError("OpenVINO gate did not distinguish text from blank input")
        messages.append(f"OpenVINO: OK ({', '.join(gate.info.execution_devices)})")

        encoded = cv2.QRCodeEncoder_create().encode("smartscan-bundle-test")
        encoded = cv2.copyMakeBorder(encoded, 16, 16, 16, 16, cv2.BORDER_CONSTANT, value=255)
        encoded = cv2.resize(encoded, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
        if QrEngine().recognize(encoded).text != "smartscan-bundle-test":
            raise RuntimeError("QR decoder round-trip failed")
        messages.append("QR: OK")

        ocr_image = np.full((320, 960, 3), 255, dtype=np.uint8)
        cv2.putText(
            ocr_image,
            "SMARTSCAN 123",
            (35, 190),
            cv2.FONT_HERSHEY_SIMPLEX,
            2.5,
            (0, 0, 0),
            6,
            cv2.LINE_AA,
        )
        smoke_log = os.environ.get("SMARTSCAN_SMOKE_LOG")
        worker_log_directory = str(Path(smoke_log).parent if smoke_log else Path.cwd() / "logs")
        with ProcessPoolExecutor(
            max_workers=1,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=initialize_ocr_worker,
            initargs=(
                "japan",
                0.2,
                settings.recognition.ocr_cpu_threads,
                worker_log_directory,
                "INFO",
            ),
        ) as executor:
            result = executor.submit(recognize_in_worker, ocr_image).result(timeout=120)
        if not result.items:
            raise RuntimeError("PaddleOCR returned no results")
        messages.append(f"PaddleOCR process: OK ({result.text!r})")
    except Exception:
        exit_code = 1
        messages.append(traceback.format_exc())

    report = "\n".join(messages) + "\n"
    log_path = os.environ.get("SMARTSCAN_SMOKE_LOG")
    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        Path(log_path).write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return exit_code
