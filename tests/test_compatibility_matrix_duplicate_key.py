"""Duplicate-key compatibility regression."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityDuplicateKeyTests(unittest.TestCase):
    def test_duplicate_key_collapses_to_one_row(self):
        records = [
            CompatibilityRecord("prod", "dj", "3.5", "map", "community", True, "direct"),
            CompatibilityRecord("prod", "dj", "3.5", "map", "community", True, "direct"),
        ]
        self.assertEqual(len(build_compatibility_matrix(records)), 1)


if __name__ == "__main__":
    unittest.main()
