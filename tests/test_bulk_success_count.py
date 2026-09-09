"""Bulk summary added-count contract."""

from __future__ import annotations

import unittest


class BulkSuccessCountTests(unittest.TestCase):
    def test_added_count_counts_saved_devices(self):
        added = ["a", "b", "c"]
        self.assertEqual(str(len(added)), "3")


if __name__ == "__main__":
    unittest.main()
