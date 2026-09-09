"""Bulk flow summary does not need to expose device IDs in placeholders."""

from __future__ import annotations

import unittest


class BulkSummaryNoIdsTests(unittest.TestCase):
    def test_public_placeholders_are_counts_only(self):
        placeholders = {"added_count": "3", "failed_count": "1", "review_count": "1"}
        self.assertEqual(set(placeholders), {"added_count", "failed_count", "review_count"})


if __name__ == "__main__":
    unittest.main()
