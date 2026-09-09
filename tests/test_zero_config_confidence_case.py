"""Zero-config confidence normalization is case-insensitive."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigConfidenceCaseTests(unittest.TestCase):
    def test_uppercase_high_is_accepted(self):
        candidate = SimpleNamespace(confidence="HIGH", config={"id": 1})
        self.assertEqual(evaluate_zero_config([candidate]).decision, ZeroConfigDecision.AUTO_CONFIGURE)


if __name__ == "__main__":
    unittest.main()
