"""Compatibility records remain product-level and never accept device identity."""

from __future__ import annotations

import inspect
import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityNoDeviceIdTests(unittest.TestCase):
    def test_record_constructor_has_no_device_id_parameter(self):
        self.assertNotIn("device_id", inspect.signature(CompatibilityRecord).parameters)


if __name__ == "__main__":
    unittest.main()
