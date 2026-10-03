"""Collect PaddleX registry modules and YAML model configurations."""

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all("paddlex", include_py_files=True)
