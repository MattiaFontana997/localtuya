"""Reason code for medium-confidence zero-config rejection."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigMediumReasonTests(unittest.TestCase):
    def test_medium_candidate_reason_is_stable(self):
        candidate = SimpleNamespace(confidence=SimpleNamespace(value="medium"), config={"id": 1})
        self.assertEqual(evaluate_zero_config([candidate]).reason, "non_high_confidence_candidate")


if __name__ == "__main__":
    unittest.main()
