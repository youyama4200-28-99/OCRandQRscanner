"""Collect OpenVINO plugins and native runtime libraries."""

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all("openvino", include_py_files=True)
