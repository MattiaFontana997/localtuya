"""Invalid confidence normalizes to experimental status."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityInvalidConfidenceTests(unittest.TestCase):
    def test_invalid_confidence_is_experimental(self):
        row = CompatibilityRecord("p", "dj", "3.5", "m", "invalid", True, "direct").public_dict()
        self.assertEqual(row["status"], "experimental")


if __name__ == "__main__":
    unittest.main()
