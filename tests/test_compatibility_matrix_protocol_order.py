"""Compatibility rows are deterministically ordered by protocol text."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityProtocolOrderTests(unittest.TestCase):
    def test_protocol_order_is_deterministic(self):
        rows = build_compatibility_matrix([
            CompatibilityRecord("p", "dj", "3.5", "m", "community", True, "direct"),
            CompatibilityRecord("p", "dj", "3.4", "m", "community", True, "direct"),
        ])
        self.assertEqual([row["protocol"] for row in rows], ["3.4", "3.5"])


if __name__ == "__main__":
    unittest.main()
