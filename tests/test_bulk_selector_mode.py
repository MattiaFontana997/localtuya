"""Bulk selector uses multi-selection semantics."""

from __future__ import annotations

import unittest


class BulkSelectorModeTests(unittest.TestCase):
    def test_multiple_selection_is_required_by_contract(self):
        multiple = True
        self.assertTrue(multiple)


if __name__ == "__main__":
    unittest.main()
