"""Non-dictionary candidate configs are never auto-configured."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigNonMappingConfigTests(unittest.TestCase):
    def test_list_config_requires_review(self):
        candidate = SimpleNamespace(confidence="high", config=[])
        self.assertEqual(evaluate_zero_config([candidate]).decision, ZeroConfigDecision.REVIEW_REQUIRED)


if __name__ == "__main__":
    unittest.main()
