"""Zero-config result decision metadata is immutable."""

from __future__ import annotations

import dataclasses
import unittest

from custom_components.localtuya.zero_config import ZeroConfigDecision, ZeroConfigResult


class ZeroConfigResultFrozenTests(unittest.TestCase):
    def test_result_dataclass_is_frozen(self):
        result = ZeroConfigResult(ZeroConfigDecision.MANUAL_REQUIRED, [], "x")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.reason = "y"


if __name__ == "__main__":
    unittest.main()
