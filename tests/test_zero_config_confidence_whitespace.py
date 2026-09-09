"""Zero-config trims confidence text."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigConfidenceWhitespaceTests(unittest.TestCase):
    def test_spaced_high_is_accepted(self):
        candidate = SimpleNamespace(confidence=" high ", config={"id": 1})
        self.assertEqual(evaluate_zero_config([candidate]).decision, ZeroConfigDecision.AUTO_CONFIGURE)


if __name__ == "__main__":
    unittest.main()
