"""Optional version evidence remains nullable."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityOptionalVersionTests(unittest.TestCase):
    def test_optional_versions_can_be_none(self):
        row = CompatibilityRecord("p", "dj", "3.5", "m", "community", True, "direct").public_dict()
        self.assertIsNone(row["home_assistant"])
        self.assertIsNone(row["localtuya"])
        self.assertIsNone(row["tested_at"])


if __name__ == "__main__":
    unittest.main()
