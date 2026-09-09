"""Protocol normalization for compatibility matrix."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityProtocolTests(unittest.TestCase):
    def test_empty_protocol_becomes_unknown(self):
        row = build_compatibility_matrix([
            CompatibilityRecord("prod", "dj", "", "map", "community", True, "direct")
        ])[0]
        self.assertEqual(row["protocol"], "unknown")


if __name__ == "__main__":
    unittest.main()
