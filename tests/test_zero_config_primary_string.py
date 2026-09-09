"""Numeric-string primary datapoints are normalized by zero-config."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class ZeroConfigPrimaryStringTests(unittest.TestCase):
    def test_numeric_string_primary_is_accepted(self):
        candidate = SimpleNamespace(confidence="high", config={"id": "20"})
        self.assertEqual(evaluate_zero_config([candidate]).decision, ZeroConfigDecision.AUTO_CONFIGURE)


if __name__ == "__main__":
    unittest.main()
