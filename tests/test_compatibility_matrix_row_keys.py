"""Public compatibility row keys are stable."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityRowKeysTests(unittest.TestCase):
    def test_row_keys_are_stable(self):
        row = build_compatibility_matrix([
            CompatibilityRecord("p", "dj", "3.5", "m", "community", True, "direct")
        ])[0]
        self.assertIn("product_id", row)
        self.assertIn("status", row)
        self.assertIn("hardware_tested", row)


if __name__ == "__main__":
    unittest.main()
