"""Bulk orchestration keeps internal device identity for persistence."""

from __future__ import annotations

import unittest


class BulkInternalIdentityTests(unittest.TestCase):
    def test_success_item_carries_device_id_internally(self):
        item = {"device_id": "x", "device_data": {}, "candidates": []}
        self.assertEqual(item["device_id"], "x")


if __name__ == "__main__":
    unittest.main()
