"""Zero-config reasons are stable strings."""

from __future__ import annotations

import unittest

from custom_components.localtuya.zero_config import evaluate_zero_config


class ZeroConfigReasonTypeTests(unittest.TestCase):
    def test_reason_is_string(self):
        self.assertIsInstance(evaluate_zero_config([]).reason, str)


if __name__ == "__main__":
    unittest.main()
