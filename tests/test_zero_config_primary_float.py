"""Integral numeric primary DPs normalize consistently."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigPrimaryFloatTests(unittest.TestCase):
    def test_integral_float_primary_is_accepted_by_integer_normalization(self):
        candidate = SimpleNamespace(confidence="high", config={"id": 1.0})
        self.assertEqual(evaluate_zero_config([candidate]).decision, ZeroConfigDecision.AUTO_CONFIGURE)


if __name__ == "__main__":
    unittest.main()
