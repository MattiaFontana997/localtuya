"""Status semantics for compatibility matrix."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityStatusTests(unittest.TestCase):
    def test_unknown_status_becomes_experimental(self):
        row = build_compatibility_matrix([
            CompatibilityRecord("prod", "dj", "3.5", "map", "other", True, "direct")
        ])[0]
        self.assertEqual(row["status"], "experimental")


if __name__ == "__main__":
    unittest.main()
