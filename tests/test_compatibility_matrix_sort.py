"""Sorting semantics for compatibility matrix."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityMatrixSortTests(unittest.TestCase):
    def test_rows_sort_by_product_protocol_transport_mapping(self):
        rows = build_compatibility_matrix([
            CompatibilityRecord("b", "x", "3.4", "m2", "community", True, "direct"),
            CompatibilityRecord("a", "x", "3.5", "m1", "community", True, "direct"),
        ])
        self.assertEqual([row["product_id"] for row in rows], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
