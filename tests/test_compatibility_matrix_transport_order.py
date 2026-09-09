"""Compatibility rows sort transport deterministically."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityTransportOrderTests(unittest.TestCase):
    def test_direct_sorts_before_gateway_child(self):
        rows = build_compatibility_matrix([
            CompatibilityRecord("p", "dj", "3.5", "m", "community", True, "gateway_child"),
            CompatibilityRecord("p", "dj", "3.5", "m", "community", True, "direct"),
        ])
        self.assertEqual([row["transport"] for row in rows], ["direct", "gateway_child"])


if __name__ == "__main__":
    unittest.main()
