"""Enum-like confidence values are normalized by zero-config."""

from __future__ import annotations

import unittest
from enum import Enum
from types import SimpleNamespace

from custom_components.localtuya.zero_config import ZeroConfigDecision, evaluate_zero_config


class _Confidence(Enum):
    HIGH = "high"


class ZeroConfigConfidenceEnumTests(unittest.TestCase):
    def test_enum_like_high_is_accepted(self):
        candidate = SimpleNamespace(confidence=_Confidence.HIGH, config={"id": 1})
        self.assertEqual(evaluate_zero_config([candidate]).decision, ZeroConfigDecision.AUTO_CONFIGURE)


if __name__ == "__main__":
    unittest.main()
