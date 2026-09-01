"""Collect PaddlePaddle's dynamic modules, native libraries, and data files."""

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all("paddle", include_py_files=True)
