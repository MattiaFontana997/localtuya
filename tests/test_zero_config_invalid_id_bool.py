"""Boolean IDs are never treated as datapoint integers."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigBooleanIdTests(unittest.TestCase):
    def test_boolean_id_requires_review(self):
        self.assertIs(evaluate_zero_config([SimpleNamespace(confidence="high", config={"id": False})]).decision, ZeroConfigDecision.REVIEW_REQUIRED)


if __name__ == "__main__":
    unittest.main()
