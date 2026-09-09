"""Version evidence fields for compatibility matrix."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityVersionFieldsTests(unittest.TestCase):
    def test_version_evidence_is_preserved(self):
        row = build_compatibility_matrix([
            CompatibilityRecord("prod", "dj", "3.5", "map", "verified", True, "direct", "2026.9", "6.7.0", "2026-09-09")
        ])[0]
        self.assertEqual(row["home_assistant"], "2026.9")
        self.assertEqual(row["localtuya"], "6.7.0")
        self.assertEqual(row["tested_at"], "2026-09-09")


if __name__ == "__main__":
    unittest.main()
