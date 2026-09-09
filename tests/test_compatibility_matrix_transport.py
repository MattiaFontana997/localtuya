"""Transport semantics for compatibility evidence."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityTransportTests(unittest.TestCase):
    def test_unknown_transport_falls_back_to_direct(self):
        row = build_compatibility_matrix([
            CompatibilityRecord("prod", "dj", "3.5", "map", "community", True, "other")
        ])[0]
        self.assertEqual(row["transport"], "direct")


if __name__ == "__main__":
    unittest.main()
