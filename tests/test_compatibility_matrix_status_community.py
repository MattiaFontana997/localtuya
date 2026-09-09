"""Community compatibility evidence stays community."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import CompatibilityRecord


class CompatibilityCommunityStatusTests(unittest.TestCase):
    def test_community_status_is_preserved(self):
        row = CompatibilityRecord("p", "dj", "3.5", "m", "community", True, "direct").public_dict()
        self.assertEqual(row["status"], "community")


if __name__ == "__main__":
    unittest.main()
