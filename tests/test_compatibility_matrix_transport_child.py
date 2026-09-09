"""Gateway-child transport is preserved in compatibility rows."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityGatewayTransportTests(unittest.TestCase):
    def test_gateway_child_transport_is_preserved(self):
        row = build_compatibility_matrix([
            CompatibilityRecord("prod", "dj", "3.4", "map", "verified", True, "gateway_child")
        ])[0]
        self.assertEqual(row["transport"], "gateway_child")


if __name__ == "__main__":
    unittest.main()
