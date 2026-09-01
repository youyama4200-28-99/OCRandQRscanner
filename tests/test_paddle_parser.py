import unittest

from smartscan.engines.paddle_ocr import parse_legacy_results, parse_predict_results


class FakeResult:
    def __init__(self, payload):
        self.json = payload


class PaddleParserTests(unittest.TestCase):
    def test_predict_result_filters_low_confidence(self) -> None:
        payload = {
            "res": {
                "rec_texts": ["採用", "noise"],
                "rec_scores": [0.91, 0.2],
                "rec_polys": [[[1, 2], [3, 2], [3, 4], [1, 4]], [[5, 6], [7, 6], [7, 8], [5, 8]]],
            }
        }
        result = parse_predict_results([FakeResult(payload)], 0.5)
        self.assertEqual(result.text, "採用")
        self.assertEqual(result.items[0].polygon[0], (1, 2))

    def test_legacy_result_is_supported(self) -> None:
        raw = [[[[[0, 0], [1, 0], [1, 1], [0, 1]], ("legacy", 0.8)]]]
        self.assertEqual(parse_legacy_results(raw, 0.5).text, "legacy")


if __name__ == "__main__":
    unittest.main()
