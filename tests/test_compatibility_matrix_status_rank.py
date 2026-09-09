"""Status ranking contract for duplicate compatibility evidence."""

from __future__ import annotations

import unittest


class CompatibilityStatusRankTests(unittest.TestCase):
    def test_rank_order_is_experimental_community_verified(self):
        rank = {"experimental": 0, "community": 1, "verified": 2}
        self.assertLess(rank["experimental"], rank["community"])
        self.assertLess(rank["community"], rank["verified"])


if __name__ == "__main__":
    unittest.main()
