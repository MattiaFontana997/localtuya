"""Experimental compatibility evidence stays experimental."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityExperimentalStatusTests(unittest.TestCase):
    def test_experimental_status_is_preserved(self):
        row = CompatibilityRecord("p", "dj", "3.5", "m", "experimental", True, "direct").public_dict()
        self.assertEqual(row["status"], "experimental")


if __name__ == "__main__":
    unittest.main()
