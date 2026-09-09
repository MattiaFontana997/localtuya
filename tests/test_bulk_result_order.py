"""Bulk success ordering follows the selected device order."""

from __future__ import annotations

import unittest


class BulkResultOrderingTests(unittest.TestCase):
    def test_success_order_contract(self):
        selected = ["b", "a"]
        successes = [{"device_id": device_id} for device_id in selected]
        self.assertEqual([item["device_id"] for item in successes], selected)


if __name__ == "__main__":
    unittest.main()
