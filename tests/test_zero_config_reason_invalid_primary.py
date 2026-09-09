"""Reason code for invalid primary DP."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigInvalidPrimaryReasonTests(unittest.TestCase):
    def test_invalid_primary_reason_is_stable(self):
        candidate = SimpleNamespace(confidence=SimpleNamespace(value="high"), config={"id": "x"})
        self.assertEqual(evaluate_zero_config([candidate]).reason, "invalid_primary_dp")


if __name__ == "__main__":
    unittest.main()
