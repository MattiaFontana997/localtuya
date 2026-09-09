"""Unknown protocol compatibility regression."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityUnknownProtocolTests(unittest.TestCase):
    def test_unknown_protocol_is_publishable(self):
        row = build_compatibility_matrix([
            CompatibilityRecord("prod", "dj", "unknown", "map", "community", True, "direct")
        ])[0]
        self.assertEqual(row["protocol"], "unknown")


if __name__ == "__main__":
    unittest.main()
