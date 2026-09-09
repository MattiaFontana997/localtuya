"""Deduplication semantics for compatibility matrix."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityDedupTests(unittest.TestCase):
    def test_stronger_duplicate_status_wins(self):
        rows = build_compatibility_matrix([
            CompatibilityRecord("prod", "dj", "3.5", "map", "community", True, "direct"),
            CompatibilityRecord("prod", "dj", "3.5", "map", "verified", True, "direct"),
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "verified")


if __name__ == "__main__":
    unittest.main()
