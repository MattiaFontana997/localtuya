"""Bulk summary count semantics."""

from __future__ import annotations

import unittest


class BulkSummaryCountTests(unittest.TestCase):
    def test_counts_are_stringified_for_flow_placeholders(self):
        added = [1, 2]
        failures = [1]
        review = [1]
        placeholders = {
            "added_count": str(len(added)),
            "failed_count": str(len(failures)),
            "review_count": str(len(review)),
        }
        self.assertEqual(placeholders, {"added_count": "2", "failed_count": "1", "review_count": "1"})


if __name__ == "__main__":
    unittest.main()
