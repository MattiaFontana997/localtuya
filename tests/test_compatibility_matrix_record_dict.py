"""Public compatibility dictionaries use status semantics."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityPublicDictTests(unittest.TestCase):
    def test_public_dict_contains_status(self):
        row = CompatibilityRecord("p", "dj", "3.5", "m", "community", True, "direct").public_dict()
        self.assertIn("status", row)
        self.assertNotIn("confidence", row)


if __name__ == "__main__":
    unittest.main()
