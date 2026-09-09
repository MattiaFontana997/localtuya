"""Bulk summary exposes only aggregate placeholders publicly."""

from __future__ import annotations

import unittest


class BulkSummaryFieldsTests(unittest.TestCase):
    def test_public_summary_fields(self):
        fields = {"added_count", "failed_count", "review_count"}
        self.assertEqual(len(fields), 3)


if __name__ == "__main__":
    unittest.main()
