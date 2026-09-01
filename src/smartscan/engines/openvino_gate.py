from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
import openvino as ov
from openvino import opset13 as ops

logger = logging.getLogger("smartscan.openvino")


@dataclass(frozen=True, slots=True)
class GateInfo:
    requested_device: str
    execution_devices: tuple[str, ...]
    available_devices: tuple[str, ...]


class OpenVinoTextGate:
    """OpenVINO graph measuring text-like edge energy in a frame."""

    def __init__(self, *, width: int = 320, height: int = 180, device: str = "AUTO") -> None:
        started_at = time.perf_counter()
        self.width = width
        self.height = height
        self.requested_device = device
        self._core = ov.Core()
        self._compiled = self._core.compile_model(self._build_model(width, height), device)
        logger.info(
            "OpenVINO gate initialized; requested_device=%s execution_devices=%s "
            "available_devices=%s elapsed_ms=%.1f",
            device,
            ",".join(self.info.execution_devices),
            ",".join(self.info.available_devices),
            (time.perf_counter() - started_at) * 1000,
        )

    @staticmethod
    def _build_model(width: int, height: int) -> ov.Model:
        image = ops.parameter([1, 1, height, width], np.float32, name="grayscale_frame")
        sobel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
        kernels = np.stack([sobel_x, sobel_x.T])[:, np.newaxis, :, :]
        edges = ops.convolution(
            image,
            ops.constant(kernels),
            strides=[1, 1],
            pads_begin=[1, 1],
            pads_end=[1, 1],
            dilations=[1, 1],
        )
        energy = ops.reduce_mean(
            ops.absolute(edges),
            ops.constant(np.array([1, 2, 3], dtype=np.int64)),
            keep_dims=False,
        )
        return ov.Model([energy], [image], "SmartScanTextEdgeGate")

    @property
    def info(self) -> GateInfo:
        try:
            execution = tuple(self._compiled.get_property("EXECUTION_DEVICES"))
        except RuntimeError:
            execution = (self.requested_device,)
        return GateInfo(self.requested_device, execution, tuple(self._core.available_devices))

    def score(self, frame: Any) -> float:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (self.width, self.height), interpolation=cv2.INTER_AREA)
        tensor = resized.astype(np.float32)[np.newaxis, np.newaxis, :, :] / 255.0
        outputs = self._compiled([tensor])
        return float(np.asarray(next(iter(outputs.values()))).reshape(-1)[0])
