"""Mapping ID remains part of compatibility evidence."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityMappingIdTests(unittest.TestCase):
    def test_mapping_id_is_preserved(self):
        row = build_compatibility_matrix([
            CompatibilityRecord("prod", "dj", "3.5", "map-123", "community", True, "direct")
        ])[0]
        self.assertEqual(row["mapping_id"], "map-123")


if __name__ == "__main__":
    unittest.main()
