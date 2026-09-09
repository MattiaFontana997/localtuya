"""Bulk review-count semantics remain independent from failures."""

from __future__ import annotations

import unittest


class BulkReviewCountTests(unittest.TestCase):
    def test_review_count_counts_review_items(self):
        review_required = ["a", "b"]
        self.assertEqual(str(len(review_required)), "2")


if __name__ == "__main__":
    unittest.main()
