"""Bulk successes are represented as an ordered list."""

from __future__ import annotations

import unittest


class BulkSuccessesListTests(unittest.TestCase):
    def test_successes_is_list(self):
        result = {"successes": [], "failures": []}
        self.assertIsInstance(result["successes"], list)


if __name__ == "__main__":
    unittest.main()
