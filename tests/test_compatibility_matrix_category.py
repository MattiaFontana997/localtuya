"""Category normalization for compatibility matrix."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityCategoryTests(unittest.TestCase):
    def test_blank_category_is_allowed_but_private_fields_are_absent(self):
        row = build_compatibility_matrix([
            CompatibilityRecord("prod", "", "3.5", "map", "community", True, "direct")
        ])[0]
        self.assertEqual(row["category"], "")
        self.assertNotIn("device_id", row)


if __name__ == "__main__":
    unittest.main()
