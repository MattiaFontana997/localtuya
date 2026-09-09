"""Compatibility public rows always expose status."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityStatusFieldTests(unittest.TestCase):
    def test_status_field_exists(self):
        row = build_compatibility_matrix([CompatibilityRecord("p", "dj", "3.5", "m", "community", True, "direct")])[0]
        self.assertIn("status", row)


if __name__ == "__main__":
    unittest.main()
