"""Protocol version is intentionally public compatibility metadata."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityPublicProtocolTests(unittest.TestCase):
    def test_protocol_is_public(self):
        self.assertEqual(CompatibilityRecord("p", "dj", "3.5", "m", "community", True, "direct").public_dict()["protocol"], "3.5")


if __name__ == "__main__":
    unittest.main()
