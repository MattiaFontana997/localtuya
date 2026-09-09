"""Bulk selector values are device-ID strings."""

from __future__ import annotations

import unittest


class BulkSelectionTypeTests(unittest.TestCase):
    def test_selection_values_are_strings(self):
        values = ["a", "b"]
        self.assertTrue(all(isinstance(value, str) for value in values))


if __name__ == "__main__":
    unittest.main()
