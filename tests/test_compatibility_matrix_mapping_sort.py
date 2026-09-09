"""Mapping ID participates in deterministic compatibility ordering."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityMappingSortTests(unittest.TestCase):
    def test_mapping_ids_sort_within_same_product_protocol(self):
        rows = build_compatibility_matrix([
            CompatibilityRecord("p", "dj", "3.5", "z", "community", True, "direct"),
            CompatibilityRecord("p", "dj", "3.5", "a", "community", True, "direct"),
        ])
        self.assertEqual([row["mapping_id"] for row in rows], ["a", "z"])


if __name__ == "__main__":
    unittest.main()
