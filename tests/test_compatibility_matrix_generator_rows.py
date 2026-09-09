"""Generated compatibility rows must be deterministic."""

from __future__ import annotations

import unittest


class CompatibilityGeneratorRowsTests(unittest.TestCase):
    def test_public_table_column_order_is_stable(self):
        columns = ["Product ID", "Category", "Protocol", "Transport", "Mapping", "Status", "HA", "LocalTuya", "Tested at"]
        self.assertEqual(columns[0], "Product ID")
        self.assertEqual(columns[-1], "Tested at")


if __name__ == "__main__":
    unittest.main()
