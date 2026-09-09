"""Compatibility matrix trims protocol strings."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityProtocolTrimTests(unittest.TestCase):
    def test_protocol_is_trimmed(self):
        row = build_compatibility_matrix([CompatibilityRecord("p", "dj", " 3.5 ", "m", "community", True, "direct")])[0]
        self.assertEqual(row["protocol"], "3.5")


if __name__ == "__main__":
    unittest.main()
