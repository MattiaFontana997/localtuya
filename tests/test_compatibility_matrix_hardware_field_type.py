"""Compatibility hardware evidence remains a boolean field."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityHardwareFieldTypeTests(unittest.TestCase):
    def test_hardware_tested_is_boolean(self):
        row = CompatibilityRecord("p", "dj", "3.5", "m", "community", True, "direct").public_dict()
        self.assertIsInstance(row["hardware_tested"], bool)


if __name__ == "__main__":
    unittest.main()
