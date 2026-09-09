"""Hardware evidence flag remains explicit in compatibility rows."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityHardwareFlagTests(unittest.TestCase):
    def test_hardware_tested_flag_is_preserved(self):
        row = build_compatibility_matrix([
            CompatibilityRecord("prod", "dj", "3.5", "map", "community", False, "direct")
        ])[0]
        self.assertFalse(row["hardware_tested"])


if __name__ == "__main__":
    unittest.main()
