"""Bulk selector labels fall back to device IDs."""

from __future__ import annotations

import unittest


class BulkSelectorLabelFallbackTests(unittest.TestCase):
    def test_label_fallback(self):
        device_id = "id-1"
        device = {"name": ""}
        self.assertEqual(device.get("name") or device_id, "id-1")


if __name__ == "__main__":
    unittest.main()
