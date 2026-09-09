"""Compatibility evidence model never accepts host data."""

from __future__ import annotations

import inspect
import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityNoHostTests(unittest.TestCase):
    def test_record_constructor_has_no_host_parameter(self):
        self.assertNotIn("host", inspect.signature(CompatibilityRecord).parameters)


if __name__ == "__main__":
    unittest.main()
