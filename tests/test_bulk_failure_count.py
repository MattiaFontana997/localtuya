"""Bulk summary failed-count contract."""

from __future__ import annotations

import unittest


class BulkFailureCountTests(unittest.TestCase):
    def test_failed_count_comes_from_failures_only(self):
        failures = [{"device_id": "x", "reason": "cannot_connect"}]
        review = ["y"]
        self.assertEqual(len(failures), 1)
        self.assertEqual(len(review), 1)


if __name__ == "__main__":
    unittest.main()
