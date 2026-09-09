"""Non-high confidence zero-config reason remains stable."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigNonHighReasonTests(unittest.TestCase):
    def test_low_candidate_uses_same_review_reason(self):
        candidate = SimpleNamespace(confidence=SimpleNamespace(value="low"), config={"id": 1})
        self.assertEqual(evaluate_zero_config([candidate]).reason, "non_high_confidence_candidate")


if __name__ == "__main__":
    unittest.main()
