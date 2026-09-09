"""Reason code for invalid zero-config candidate config."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigInvalidConfigReasonTests(unittest.TestCase):
    def test_empty_config_reason_is_stable(self):
        candidate = SimpleNamespace(confidence=SimpleNamespace(value="high"), config={})
        self.assertEqual(evaluate_zero_config([candidate]).reason, "invalid_candidate_config")


if __name__ == "__main__":
    unittest.main()
