from __future__ import annotations

import logging
import multiprocessing
import threading
import time
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..camera import Camera, discover_camera_indices
from ..config import AppSettings
from ..controller import AutoSwitchPolicy
from ..engines.openvino_gate import OpenVinoTextGate
from ..engines.paddle_ocr import initialize_ocr_worker, recognize_in_worker
from ..engines.qr import QrEngine
from ..models import RecognitionResult, ScanMode

logger = logging.getLogger("smartscan.ui")


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: AppSettings,
        *,
        log_path: Path | None = None,
        log_level: str = "INFO",
    ) -> None:
        super().__init__()
        self.settings = settings
        self._log_path = log_path
        self.setWindowTitle(settings.ui.window_title)
        self.resize(1180, 760)
        self._camera = Camera(settings.camera)
        recognition = settings.recognition
        self._qr = QrEngine(max_width=recognition.qr_max_width)
        log_directory = str(log_path.parent if log_path else Path.cwd() / "logs")
        self._executor = ProcessPoolExecutor(
            max_workers=1,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=initialize_ocr_worker,
            initargs=(
                recognition.language,
                recognition.minimum_confidence,
                recognition.ocr_cpu_threads,
                log_directory,
                log_level,
            ),
        )
        self._ocr_future: Future[RecognitionResult] | None = None
        self._camera_scan_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="camera-discovery"
        )
        self._camera_scan_future: Future[tuple[int, ...]] | None = None
        self._updating_camera_combo = False
        self._last_ocr_result = RecognitionResult()
        self._last_ocr_result_at = 0.0
        self._last_text = ""
        self._frame_count = 0
        self._last_qr_result = RecognitionResult()
        self._last_gate_score = 0.0
        self._tick_started_at = 0.0
        self._tick_stage = "idle"
        self._last_tick_duration = 0.0
        self._watchdog_stop = threading.Event()
        self._gate: OpenVinoTextGate | None = None
        self._policy = AutoSwitchPolicy(
            text_score_threshold=settings.recognition.text_score_threshold,
            qr_hold_seconds=settings.recognition.qr_hold_seconds,
            ocr_interval_seconds=settings.recognition.ocr_interval_seconds,
        )
        self._build_ui()
        self._initialize_gate()
        self._watchdog = threading.Thread(
            target=self._watch_for_stall,
            name="ui-stall-watchdog",
            daemon=True,
        )
        self._watchdog.start()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(max(15, round(1000 / settings.camera.fps)))
        if not self._camera.open():
            self._show_camera_error()
        self._start_camera_scan()
        logger.info("MainWindow initialized")

    def _build_ui(self) -> None:
        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(18)
        preview_panel = QFrame(objectName="previewPanel")
        preview_layout = QVBoxLayout(preview_panel)
        self.preview = QLabel("カメラを起動しています…")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(640, 480)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview_layout.addWidget(self.preview)
        outer.addWidget(preview_panel, 3)

        side = QFrame(objectName="sidePanel")
        side.setMinimumWidth(310)
        layout = QVBoxLayout(side)
        title = QLabel("SmartScan", objectName="title")
        subtitle = QLabel("QR / OCR 自動認識", objectName="subtitle")
        self.mode_label = QLabel(ScanMode.STARTING.value, objectName="modeBadge")
        camera_title = QLabel("カメラ", objectName="sectionTitle")
        camera_row = QHBoxLayout()
        self.camera_combo = QComboBox()
        self.camera_combo.addItem(
            f"カメラ {self.settings.camera.index}", self.settings.camera.index
        )
        self.camera_combo.currentIndexChanged.connect(self._on_camera_selected)
        self.camera_scan_button = QPushButton("再検索")
        self.camera_scan_button.clicked.connect(self._start_camera_scan)
        camera_row.addWidget(self.camera_combo, 1)
        camera_row.addWidget(self.camera_scan_button)
        self.camera_status_label = QLabel("カメラを確認中…")
        self.camera_status_label.setWordWrap(True)
        self.engine_label = QLabel("AIエンジンを準備中")
        self.engine_label.setWordWrap(True)
        self.score_label = QLabel("文字スコア: --")
        result_title = QLabel("認識結果", objectName="sectionTitle")
        self.result_box = QPlainTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setPlaceholderText("QRコードまたは文字をカメラに映してください")
        button_row = QHBoxLayout()
        copy_button = QPushButton("コピー")
        copy_button.clicked.connect(self._copy_result)
        clear_button = QPushButton("クリア")
        clear_button.clicked.connect(self._clear_result)
        button_row.addWidget(copy_button)
        button_row.addWidget(clear_button)
        reconnect_button = QPushButton("カメラを再接続")
        reconnect_button.clicked.connect(self._reconnect_camera)
        log_button = QPushButton("ログフォルダーを開く")
        log_button.setEnabled(self._log_path is not None)
        log_button.clicked.connect(self._open_log_directory)
        for widget in (title, subtitle, self.mode_label, camera_title):
            layout.addWidget(widget)
        layout.addLayout(camera_row)
        layout.addWidget(self.camera_status_label)
        layout.addWidget(self.engine_label)
        layout.addWidget(self.score_label)
        layout.addSpacing(10)
        layout.addWidget(result_title)
        layout.addWidget(self.result_box, 1)
        layout.addLayout(button_row)
        layout.addWidget(reconnect_button)
        layout.addWidget(log_button)
        outer.addWidget(side, 1)
        self.setCentralWidget(root)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #101418; color: #e8eef3; font-size: 14px; }
            QFrame#previewPanel, QFrame#sidePanel { background: #171d23; border-radius: 12px; }
            QLabel#title { font-size: 28px; font-weight: 700; color: white; }
            QLabel#subtitle { color: #91a1af; }
            QLabel#sectionTitle { font-weight: 700; font-size: 16px; }
            QLabel#modeBadge { background: #163d52; color: #62d5ff; border-radius: 8px;
                padding: 9px 12px; font-weight: 700; font-size: 18px; }
            QPlainTextEdit { background: #0d1115; border: 1px solid #2b3741;
                border-radius: 8px; padding: 8px; selection-background-color: #225f7c; }
            QComboBox { background: #0d1115; border: 1px solid #2b3741;
                border-radius: 7px; padding: 8px; color: white; }
            QComboBox QAbstractItemView { background: #171d23; color: white;
                selection-background-color: #225f7c; }
            QPushButton { background: #237da3; border: 0; border-radius: 7px;
                padding: 9px 12px; color: white; font-weight: 600; }
            QPushButton:hover { background: #2e91ba; }
        """)

    def _initialize_gate(self) -> None:
        recognition = self.settings.recognition
        try:
            self._gate = OpenVinoTextGate(
                width=recognition.gate_width,
                height=recognition.gate_height,
                device=recognition.openvino_device,
            )
            devices = ", ".join(self._gate.info.execution_devices)
            self.engine_label.setText(f"OpenVINO: {devices}\nPaddleOCR: 初回OCR時に初期化")
        except Exception as exc:
            logger.exception("OpenVINO initialization failed; continuing without gate")
            self.engine_label.setText(
                f"OpenVINO初期化失敗: {type(exc).__name__}: {exc}\nOCRゲートを常時許可"
            )

    def _tick(self) -> None:
        started_at = time.monotonic()
        self._tick_started_at = started_at
        self._tick_stage = "collect_ocr_result"
        try:
            self._process_tick()
        except Exception:
            logger.exception("Unexpected frame processing error; stage=%s", self._tick_stage)
            self.engine_label.setText(f"フレーム処理エラー: {self._tick_stage}（ログを確認）")
        finally:
            duration = time.monotonic() - started_at
            self._last_tick_duration = duration
            self._tick_started_at = 0.0
            self._tick_stage = "idle"
            if duration >= 0.5:
                logger.warning("Slow UI frame; elapsed_ms=%.1f", duration * 1000)

    def _process_tick(self) -> None:
        self._collect_camera_scan_result()
        self._collect_ocr_result()
        self._tick_stage = "camera_read"
        stage_started_at = time.perf_counter()
        ok, frame = self._camera.read()
        self._log_slow_stage("camera_read", stage_started_at, 0.2)
        if not ok:
            return
        if self.settings.ui.mirror_preview:
            frame = cv2.flip(frame, 1)
        now = time.monotonic()
        self._frame_count += 1
        if (self._frame_count - 1) % self.settings.recognition.qr_scan_interval_frames == 0:
            self._tick_stage = "qr_recognition"
            stage_started_at = time.perf_counter()
            self._last_qr_result = self._qr.recognize(frame)
            self._log_slow_stage("qr_recognition", stage_started_at, 0.1)
        qr_result = self._last_qr_result
        if self._gate is None:
            self._last_gate_score = self.settings.recognition.text_score_threshold
        elif self._frame_count % 3 == 1:
            try:
                self._tick_stage = "openvino_gate"
                stage_started_at = time.perf_counter()
                self._last_gate_score = self._gate.score(frame)
                self._log_slow_stage("openvino_gate", stage_started_at, 0.1)
            except Exception as exc:
                logger.exception("OpenVINO gate inference failed; disabling gate")
                self.engine_label.setText(f"OpenVINO推論失敗: {exc}\nOCRゲートを常時許可")
                self._gate = None
        decision = self._policy.decide(
            now=now,
            qr_found=bool(qr_result.items),
            text_score=self._last_gate_score,
            ocr_busy=self._ocr_future is not None,
        )
        self._set_mode(decision.mode)
        self.score_label.setText(f"文字スコア: {self._last_gate_score:.4f}")
        overlay_result = RecognitionResult()
        if qr_result.items:
            overlay_result = qr_result
            self._publish("QR", qr_result)
        elif decision.run_ocr:
            self.engine_label.setText("PaddleOCR: 認識中…")
            logger.info("Submitting PaddleOCR job; frame=%d", self._frame_count)
            self._ocr_future = self._executor.submit(recognize_in_worker, frame.copy())
        elif now - self._last_ocr_result_at < self.settings.recognition.result_hold_seconds:
            overlay_result = self._last_ocr_result
        self._tick_stage = "preview_render"
        stage_started_at = time.perf_counter()
        self._draw_polygons(frame, overlay_result, decision.mode)
        self._show_frame(frame)
        self._log_slow_stage("preview_render", stage_started_at, 0.1)

    @staticmethod
    def _log_slow_stage(name: str, started_at: float, threshold_seconds: float) -> None:
        elapsed = time.perf_counter() - started_at
        if elapsed >= threshold_seconds:
            logger.warning("Slow processing stage; stage=%s elapsed_ms=%.1f", name, elapsed * 1000)

    def _watch_for_stall(self) -> None:
        reported_start = 0.0
        while not self._watchdog_stop.wait(1.0):
            started_at = self._tick_started_at
            if reported_start and started_at != reported_start:
                logger.warning(
                    "UI frame processing recovered; elapsed_seconds=%.1f",
                    self._last_tick_duration,
                )
                reported_start = 0.0
            if started_at and time.monotonic() - started_at >= 3.0:
                if reported_start != started_at:
                    reported_start = started_at
                    logger.warning(
                        "UI frame processing appears stalled; stage=%s elapsed_seconds=%.1f",
                        self._tick_stage,
                        time.monotonic() - started_at,
                    )

    def _collect_ocr_result(self) -> None:
        future = self._ocr_future
        if future is None or not future.done():
            return
        self._ocr_future = None
        self._policy.ocr_completed(time.monotonic())
        try:
            result = future.result()
            self._last_ocr_result = result
            self._last_ocr_result_at = time.monotonic()
            if result.items:
                self._publish("OCR", result)
            device = ", ".join(self._gate.info.execution_devices) if self._gate else "無効"
            self.engine_label.setText(f"OpenVINO: {device}\nPaddleOCR: 利用可能")
        except Exception as exc:
            logger.exception("PaddleOCR future failed")
            self.engine_label.setText(f"PaddleOCRエラー: {type(exc).__name__}: {exc}")

    def _publish(self, kind: str, result: RecognitionResult) -> None:
        text = result.text
        if not text or text == self._last_text:
            return
        self._last_text = text
        logger.info(
            "Recognition result published; kind=%s items=%d average_confidence=%.3f",
            kind,
            len(result.items),
            result.average_confidence,
        )
        self.result_box.setPlainText(
            f"[{kind}]  信頼度 {result.average_confidence * 100:.1f}%\n\n{text}"
        )

    def _set_mode(self, mode: ScanMode) -> None:
        self.mode_label.setText(mode.value)
        colors = {
            ScanMode.QR: ("#123f2d", "#64e6a5"),
            ScanMode.OCR: ("#3d3212", "#ffd166"),
            ScanMode.SEARCHING: ("#163d52", "#62d5ff"),
        }
        background, foreground = colors.get(mode, ("#3b2630", "#ff8fa3"))
        self.mode_label.setStyleSheet(
            f"background:{background};color:{foreground};border-radius:8px;"
            "padding:9px 12px;font-weight:700;font-size:18px;"
        )

    @staticmethod
    def _draw_polygons(frame: Any, result: RecognitionResult, mode: ScanMode) -> None:
        color = (70, 230, 140) if mode is ScanMode.QR else (70, 190, 255)
        for item in result.items:
            if len(item.polygon) >= 2:
                points = np.asarray(item.polygon, dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [points], True, color, 2, cv2.LINE_AA)

    def _show_frame(self, frame: Any) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(
            rgb.data, width, height, channels * width, QImage.Format.Format_RGB888
        ).copy()
        self.preview.setPixmap(
            QPixmap.fromImage(image).scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _copy_result(self) -> None:
        QApplication.clipboard().setText(self.result_box.toPlainText())

    def _clear_result(self) -> None:
        self.result_box.clear()
        self._last_text = ""

    def _reconnect_camera(self) -> None:
        logger.info("Camera reconnect requested by user")
        if not self._camera.open():
            self._show_camera_error()

    def _start_camera_scan(self) -> None:
        if self._camera_scan_future is not None:
            return
        excluded = frozenset({self._camera.current_index}) if self._camera.is_open else frozenset()
        self.camera_scan_button.setEnabled(False)
        self.camera_status_label.setText("利用可能なカメラを検索中…")
        self._camera_scan_future = self._camera_scan_executor.submit(
            discover_camera_indices,
            self.settings.camera.scan_max_index,
            excluded_indices=excluded,
        )

    def _collect_camera_scan_result(self) -> None:
        future = self._camera_scan_future
        if future is None or not future.done():
            return
        self._camera_scan_future = None
        self.camera_scan_button.setEnabled(True)
        try:
            indices = set(future.result())
            if self._camera.is_open:
                indices.add(self._camera.current_index)
            if not indices:
                indices.add(self.settings.camera.index)
            self._populate_camera_combo(sorted(indices), self._camera.current_index)
            self.camera_status_label.setText(f"{len(indices)}台のカメラを検出")
        except Exception:
            logger.exception("Camera discovery failed")
            self.camera_status_label.setText("カメラの検索に失敗しました（ログを確認）")

    def _populate_camera_combo(self, indices: list[int], selected_index: int) -> None:
        self._updating_camera_combo = True
        try:
            self.camera_combo.clear()
            selected_combo_index = 0
            for combo_index, camera_index in enumerate(indices):
                self.camera_combo.addItem(f"カメラ {camera_index}", camera_index)
                if camera_index == selected_index:
                    selected_combo_index = combo_index
            self.camera_combo.setCurrentIndex(selected_combo_index)
        finally:
            self._updating_camera_combo = False

    def _on_camera_selected(self, combo_index: int) -> None:
        if self._updating_camera_combo or combo_index < 0:
            return
        camera_index = self.camera_combo.itemData(combo_index)
        if not isinstance(camera_index, int) or camera_index == self._camera.current_index:
            return
        previous_index = self._camera.current_index
        self.camera_status_label.setText(f"カメラ {camera_index} に切り替え中…")
        logger.info(
            "Camera selection changed; previous_index=%d requested_index=%d",
            previous_index,
            camera_index,
        )
        if self._camera.open(camera_index):
            self._last_qr_result = RecognitionResult()
            self.camera_status_label.setText(f"カメラ {camera_index} を使用中")
            return

        logger.error("Selected camera could not be opened; index=%d", camera_index)
        restored = self._camera.open(previous_index)
        self._select_camera_combo_value(previous_index)
        if restored:
            self.camera_status_label.setText(
                f"カメラ {camera_index} を開けないため、カメラ {previous_index} に戻しました"
            )
        else:
            self._show_camera_error(camera_index)

    def _select_camera_combo_value(self, camera_index: int) -> None:
        for combo_index in range(self.camera_combo.count()):
            if self.camera_combo.itemData(combo_index) == camera_index:
                self._updating_camera_combo = True
                try:
                    self.camera_combo.setCurrentIndex(combo_index)
                finally:
                    self._updating_camera_combo = False
                return

    def _open_log_directory(self) -> None:
        if self._log_path is None:
            return
        logger.info("Opening log directory; path=%s", self._log_path.parent)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._log_path.parent)))

    def _show_camera_error(self, camera_index: int | None = None) -> None:
        camera_index = self._camera.current_index if camera_index is None else camera_index
        logger.error("Camera is unavailable; index=%d", camera_index)
        self._set_mode(ScanMode.ERROR)
        self.preview.setText(
            f"カメラ {camera_index} を開けません。\n"
            "他のアプリが使用していないか確認し、再接続してください。"
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        logger.info("Application close requested")
        self._timer.stop()
        self._watchdog_stop.set()
        self._camera.close()
        self._camera_scan_executor.shutdown(wait=False, cancel_futures=True)
        self._executor.shutdown(wait=False, cancel_futures=True)
        event.accept()
