"""Compatibility evidence model never accepts local keys."""

from __future__ import annotations

import inspect
import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityNoLocalKeyTests(unittest.TestCase):
    def test_record_constructor_has_no_local_key_parameter(self):
        self.assertNotIn("local_key", inspect.signature(CompatibilityRecord).parameters)


if __name__ == "__main__":
    unittest.main()
