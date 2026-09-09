"""Test date remains part of public compatibility evidence."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityTestedAtTests(unittest.TestCase):
    def test_tested_at_is_preserved(self):
        row = CompatibilityRecord("p", "dj", "3.5", "m", "verified", True, "direct", tested_at="2026-09-09").public_dict()
        self.assertEqual(row["tested_at"], "2026-09-09")


if __name__ == "__main__":
    unittest.main()
