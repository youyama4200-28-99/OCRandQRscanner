# Third-Party Notices

SmartScan itself is distributed under the MIT License. The Windows binary is a
collection that also contains unmodified third-party components under their own
licenses. Those licenses apply only to their respective components.

## Direct runtime dependencies

| Component | Version | License | Project |
| --- | ---: | --- | --- |
| NumPy | 2.3.5 | BSD-3-Clause | <https://numpy.org/> |
| OpenCV Python | 4.10.0.84 | Apache-2.0 and bundled third-party notices | <https://github.com/opencv/opencv-python> |
| OpenVINO | 2026.3.1 | Apache-2.0 and bundled third-party notices | <https://github.com/openvinotoolkit/openvino> |
| PaddleOCR | 3.7.0 | Apache-2.0 | <https://github.com/PaddlePaddle/PaddleOCR> |
| PaddlePaddle | 3.3.1 | Apache-2.0 | <https://github.com/PaddlePaddle/Paddle> |
| PySide6 / Qt for Python | 6.11.2 | LGPL-3.0-only, GPL-2.0-only, GPL-3.0-only, or a commercial Qt license | <https://doc.qt.io/qtforpython-6/> |

The PP-OCR models downloaded at first use are not stored in this repository or
the release archive. Their model cards identify them as Apache-2.0 licensed.

## Qt / PySide6 LGPL notice

The distributed Windows build uses PySide6 and Qt 6 under the GNU Lesser
General Public License version 3. Qt is dynamically loaded from separate DLLs
under `_internal/PySide6`; SmartScan does not modify those libraries. Recipients
may replace those DLLs with compatible modified builds and may reverse engineer
SmartScan only to the extent necessary to debug such modifications, as allowed
by LGPL-3.0.

The LGPL-3.0 and incorporated GPL-3.0 texts are included in the `licenses`
directory. Source code for the exact PySide6/Qt version can be obtained from the
official Qt repositories:

- PySide6: <https://code.qt.io/cgit/pyside/pyside-setup.git/>
- Qt 6 modules: <https://code.qt.io/cgit/qt/>
- Qt source packages: <https://download.qt.io/official_releases/qt/6.11/6.11.2/submodules/>

The application source and build instructions are available in this repository.
Do not remove or rename `_internal/PySide6` in a binary distribution; keeping it
separate is what permits replacement of the Qt shared libraries.

## License files in the Windows bundle

PyInstaller preserves distribution metadata and upstream license/notice files
under `_internal/*dist-info*`. In particular, consult:

- `_internal/opencv_contrib_python-4.10.0.84.dist-info/`
- `_internal/openvino-2026.3.1.dist-info/`
- `_internal/paddleocr-3.7.0.dist-info/`
- `_internal/paddlepaddle-3.3.1.dist-info/`
- `_internal/paddlex-3.7.2.dist-info/`
- `_internal/numpy-2.3.5.dist-info/`
- `_internal/pyside6-6.11.2.dist-info/`
- `_internal/pyside6_essentials-6.11.2.dist-info/`
- `_internal/pyside6_addons-6.11.2.dist-info/`
- `_internal/shiboken6-6.11.2.dist-info/`

Transitive dependencies retain their own copyright and license terms. When
preparing a release, distribute the complete `SmartScan` directory rather than
only `SmartScan.exe`, so these files and replaceable libraries remain present.
