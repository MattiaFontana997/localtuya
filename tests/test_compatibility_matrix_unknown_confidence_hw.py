"""Hardware evidence never promotes an unknown catalog status."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityUnknownConfidenceHardwareTests(unittest.TestCase):
    def test_unknown_confidence_with_hardware_is_experimental(self):
        row = CompatibilityRecord("p", "dj", "3.5", "m", "x", True, "direct").public_dict()
        self.assertEqual(row["status"], "experimental")


if __name__ == "__main__":
    unittest.main()
