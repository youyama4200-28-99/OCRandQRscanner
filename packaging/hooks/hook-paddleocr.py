"""Collect PaddleOCR pipelines loaded from registries at runtime."""

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all("paddleocr", include_py_files=True)
