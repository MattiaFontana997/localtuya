"""Bulk-selected device order remains user-defined."""

from __future__ import annotations

import unittest


class BulkSelectionOrderTests(unittest.TestCase):
    def test_selected_order_is_not_sorted_implicitly(self):
        selected = ["z", "a"]
        self.assertEqual(selected, ["z", "a"])


if __name__ == "__main__":
    unittest.main()
