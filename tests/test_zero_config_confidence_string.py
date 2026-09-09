"""Zero-config confidence normalization accepts enum-like values."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigConfidenceStringTests(unittest.TestCase):
    def test_plain_high_string_is_accepted(self):
        candidate = SimpleNamespace(confidence="high", config={"id": 1})
        self.assertEqual(evaluate_zero_config([candidate]).decision, ZeroConfigDecision.AUTO_CONFIGURE)


if __name__ == "__main__":
    unittest.main()
