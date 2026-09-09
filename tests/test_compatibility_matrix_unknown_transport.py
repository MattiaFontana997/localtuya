"""Unknown compatibility transport normalizes safely."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityUnknownTransportTests(unittest.TestCase):
    def test_public_record_keeps_raw_until_matrix_normalization(self):
        row = CompatibilityRecord("p", "dj", "3.5", "m", "community", True, "other").public_dict()
        self.assertEqual(row["transport"], "other")


if __name__ == "__main__":
    unittest.main()
