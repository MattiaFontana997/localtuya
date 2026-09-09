"""Compatibility matrix trims mapping IDs."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityMappingTrimTests(unittest.TestCase):
    def test_mapping_id_is_trimmed(self):
        row = build_compatibility_matrix([CompatibilityRecord("p", "dj", "3.5", "  map  ", "community", True, "direct")])[0]
        self.assertEqual(row["mapping_id"], "map")


if __name__ == "__main__":
    unittest.main()
