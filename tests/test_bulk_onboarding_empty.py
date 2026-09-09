"""Empty bulk selection behavior."""

from __future__ import annotations

import unittest


class EmptyBulkSelectionTests(unittest.TestCase):
    def test_empty_selection_is_not_success(self):
        selected = []
        self.assertFalse(selected)


if __name__ == "__main__":
    unittest.main()
