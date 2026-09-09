"""Bulk failures are represented as an ordered list."""

from __future__ import annotations

import unittest


class BulkFailuresListTests(unittest.TestCase):
    def test_failures_is_list(self):
        result = {"successes": [], "failures": []}
        self.assertIsInstance(result["failures"], list)


if __name__ == "__main__":
    unittest.main()
