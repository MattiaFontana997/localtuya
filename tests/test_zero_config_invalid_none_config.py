"""None candidate config is never auto-configured."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigNoneConfigTests(unittest.TestCase):
    def test_none_config_requires_review(self):
        candidate = SimpleNamespace(confidence="high", config=None)
        self.assertEqual(evaluate_zero_config([candidate]).decision, ZeroConfigDecision.REVIEW_REQUIRED)


if __name__ == "__main__":
    unittest.main()
