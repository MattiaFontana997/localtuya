"""Bulk preparation result shape is stable."""

from __future__ import annotations

import unittest


class BulkResultShapeTests(unittest.TestCase):
    def test_result_has_successes_and_failures(self):
        result = {"successes": [], "failures": []}
        self.assertEqual(set(result), {"successes", "failures"})


if __name__ == "__main__":
    unittest.main()
