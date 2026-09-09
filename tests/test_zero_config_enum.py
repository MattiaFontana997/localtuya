"""Zero-config decision enum values are stable."""

from __future__ import annotations

import unittest

from custom_components.localtuya.zero_config import ZeroConfigDecision


class ZeroConfigEnumTests(unittest.TestCase):
    def test_enum_values_are_stable(self):
        self.assertEqual(ZeroConfigDecision.AUTO_CONFIGURE.value, "auto_configure")
        self.assertEqual(ZeroConfigDecision.REVIEW_REQUIRED.value, "review_required")
        self.assertEqual(ZeroConfigDecision.MANUAL_REQUIRED.value, "manual_required")


if __name__ == "__main__":
    unittest.main()
