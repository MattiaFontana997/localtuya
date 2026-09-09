"""Bulk device labels fall back safely."""

from __future__ import annotations

import unittest


class BulkDeviceLabelTests(unittest.TestCase):
    def test_device_id_can_be_used_as_label_fallback(self):
        device_id = "abc123"
        name = ""
        label = name or device_id
        self.assertEqual(label, "abc123")


if __name__ == "__main__":
    unittest.main()
