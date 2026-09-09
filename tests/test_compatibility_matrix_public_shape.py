"""Public shape regression for compatibility matrix rows."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityPublicShapeTests(unittest.TestCase):
    def test_confidence_is_replaced_by_public_status(self):
        row = CompatibilityRecord("p", "dj", "3.5", "m", "verified", True, "direct").public_dict()
        self.assertNotIn("confidence", row)
        self.assertEqual(row["status"], "verified")


if __name__ == "__main__":
    unittest.main()
