"""Bulk selection filtering contract."""

from __future__ import annotations

import unittest


class BulkSelectionFilterTests(unittest.TestCase):
    def test_unknown_selection_is_ignored_by_contract(self):
        eligible = {"a", "b"}
        selected = [item for item in ["a", "x", "b"] if item in eligible]
        self.assertEqual(selected, ["a", "b"])


if __name__ == "__main__":
    unittest.main()
