"""Compatibility evidence records are immutable."""

from __future__ import annotations

import dataclasses
import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityRecordFrozenTests(unittest.TestCase):
    def test_record_is_frozen(self):
        record = CompatibilityRecord("p", "dj", "3.5", "m", "community", True, "direct")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.product_id = "other"


if __name__ == "__main__":
    unittest.main()
