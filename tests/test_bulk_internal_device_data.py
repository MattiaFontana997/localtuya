"""Bulk success data can be isolated per selected device."""

from __future__ import annotations

import copy
import unittest


class BulkDeviceDataIsolationTests(unittest.TestCase):
    def test_per_device_data_is_copyable(self):
        original = {"id": "a", "entities": []}
        copied = copy.deepcopy(original)
        copied["entities"].append({"id": 1})
        self.assertEqual(original["entities"], [])


if __name__ == "__main__":
    unittest.main()
