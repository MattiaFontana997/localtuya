"""Review-required decisions expose a stable reason."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigReviewReasonTests(unittest.TestCase):
    def test_medium_confidence_requires_review(self):
        result = evaluate_zero_config([SimpleNamespace(confidence="medium", config={"id": 1})])
        self.assertIs(result.decision, ZeroConfigDecision.REVIEW_REQUIRED)
        self.assertEqual(result.reason, "non_high_confidence_candidate")


if __name__ == "__main__":
    unittest.main()
