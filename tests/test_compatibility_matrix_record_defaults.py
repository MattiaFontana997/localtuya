"""Compatibility record optional defaults remain stable."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityRecordDefaultsTests(unittest.TestCase):
    def test_optional_version_fields_default_to_none(self):
        record = CompatibilityRecord("p", "dj", "3.5", "m", "community", True, "direct")
        self.assertIsNone(record.home_assistant)
        self.assertIsNone(record.localtuya)
        self.assertIsNone(record.tested_at)


if __name__ == "__main__":
    unittest.main()
