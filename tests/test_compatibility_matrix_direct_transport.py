"""Direct compatibility transport remains explicit."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord, build_compatibility_matrix


class CompatibilityDirectTransportTests(unittest.TestCase):
    def test_direct_transport_is_preserved(self):
        row = build_compatibility_matrix([
            CompatibilityRecord("p", "dj", "3.5", "m", "community", True, "direct")
        ])[0]
        self.assertEqual(row["transport"], "direct")


if __name__ == "__main__":
    unittest.main()
