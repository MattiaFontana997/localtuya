"""Compatibility evidence model has no account-token fields."""

from __future__ import annotations

import inspect
import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityNoTokenTests(unittest.TestCase):
    def test_record_constructor_has_no_token_parameter(self):
        params = inspect.signature(CompatibilityRecord).parameters
        self.assertNotIn("access_token", params)
        self.assertNotIn("refresh_token", params)


if __name__ == "__main__":
    unittest.main()
