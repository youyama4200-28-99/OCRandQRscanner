import unittest

import cv2
import numpy as np

from smartscan.engines.openvino_gate import OpenVinoTextGate
from smartscan.engines.qr import QrEngine


class EngineTests(unittest.TestCase):
    def test_openvino_gate_separates_text_from_blank(self) -> None:
        gate = OpenVinoTextGate(width=320, height=180, device="CPU")
        blank = np.zeros((180, 320, 3), dtype=np.uint8)
        text = blank.copy()
        cv2.putText(text, "SMARTSCAN", (12, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
        self.assertLess(gate.score(blank), 0.001)
        self.assertGreater(gate.score(text), 0.018)

    @unittest.skipUnless(hasattr(cv2, "QRCodeEncoder_create"), "OpenCV QR encoder unavailable")
    def test_qr_round_trip(self) -> None:
        encoded = cv2.QRCodeEncoder_create().encode("smartscan-test")
        encoded = cv2.copyMakeBorder(encoded, 16, 16, 16, 16, cv2.BORDER_CONSTANT, value=255)
        encoded = cv2.resize(encoded, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
        self.assertEqual(QrEngine().recognize(encoded).text, "smartscan-test")


if __name__ == "__main__":
    unittest.main()
