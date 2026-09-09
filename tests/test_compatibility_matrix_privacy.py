"""Privacy constraints for compatibility matrix records."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityMatrixPrivacyTests(unittest.TestCase):
    def test_public_rows_are_product_level_only(self):
        rows = build_compatibility_matrix(
            [CompatibilityRecord("prod", "dj", "3.5", "map", "verified", True, "direct")]
        )
        self.assertEqual(
            set(rows[0]),
            {
                "product_id",
                "category",
                "protocol",
                "mapping_id",
                "hardware_tested",
                "transport",
                "home_assistant",
                "localtuya",
                "tested_at",
                "status",
            },
        )


if __name__ == "__main__":
    unittest.main()
