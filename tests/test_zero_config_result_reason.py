"""Zero-config result always carries a stable reason code."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigResultReasonTests(unittest.TestCase):
    def test_success_reason_is_nonempty(self):
        result = evaluate_zero_config([SimpleNamespace(confidence="high", config={"id": 1})])
        self.assertTrue(result.reason)


if __name__ == "__main__":
    unittest.main()
