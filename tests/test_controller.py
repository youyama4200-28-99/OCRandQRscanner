import unittest

from smartscan.controller import AutoSwitchPolicy
from smartscan.models import ScanMode


class AutoSwitchPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = AutoSwitchPolicy(
            text_score_threshold=0.02, qr_hold_seconds=1.0, ocr_interval_seconds=1.5
        )

    def test_qr_has_priority_and_is_held(self) -> None:
        first = self.policy.decide(now=10.0, qr_found=True, text_score=1.0, ocr_busy=False)
        held = self.policy.decide(now=10.5, qr_found=False, text_score=1.0, ocr_busy=False)
        self.assertEqual(first.mode, ScanMode.QR)
        self.assertEqual(held.mode, ScanMode.QR)
        self.assertFalse(first.run_ocr)

    def test_ocr_is_throttled(self) -> None:
        first = self.policy.decide(now=1.0, qr_found=False, text_score=0.5, ocr_busy=False)
        second = self.policy.decide(now=1.1, qr_found=False, text_score=0.5, ocr_busy=False)
        self.policy.ocr_completed(now=2.0)
        third = self.policy.decide(now=2.6, qr_found=False, text_score=0.5, ocr_busy=False)
        fourth = self.policy.decide(now=3.5, qr_found=False, text_score=0.5, ocr_busy=False)
        self.assertTrue(first.run_ocr)
        self.assertFalse(second.run_ocr)
        self.assertFalse(third.run_ocr)
        self.assertTrue(fourth.run_ocr)

    def test_blank_frame_stays_in_search_mode(self) -> None:
        decision = self.policy.decide(now=1.0, qr_found=False, text_score=0.001, ocr_busy=False)
        self.assertEqual(decision.mode, ScanMode.SEARCHING)


if __name__ == "__main__":
    unittest.main()
