"""Invalid candidate configs use a stable zero-config reason."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigInvalidConfigReasonContract(unittest.TestCase):
    def test_none_config_reason_is_invalid_candidate_config(self):
        candidate = SimpleNamespace(confidence="high", config=None)
        self.assertEqual(evaluate_zero_config([candidate]).reason, "invalid_candidate_config")


if __name__ == "__main__":
    unittest.main()
