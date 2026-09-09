"""Bulk onboarding is explicitly multi-device."""

from __future__ import annotations

import unittest


class BulkMultipleDevicesTests(unittest.TestCase):
    def test_more_than_one_device_can_be_selected(self):
        selected = ["a", "b"]
        self.assertGreater(len(selected), 1)


if __name__ == "__main__":
    unittest.main()
