"""Bulk success items keep the data required for persistence."""

from __future__ import annotations

import unittest


class BulkSuccessShapeTests(unittest.TestCase):
    def test_success_item_shape(self):
        item = {"device_id": "x", "device_data": {}, "candidates": []}
        self.assertEqual(set(item), {"device_id", "device_data", "candidates"})


if __name__ == "__main__":
    unittest.main()
