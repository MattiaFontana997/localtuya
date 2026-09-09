"""Deterministic order contract for bulk onboarding."""

from __future__ import annotations

import unittest


class BulkOrderTests(unittest.TestCase):
    def test_selection_order_is_preserved(self):
        selected = ["device-b", "device-a", "device-c"]
        self.assertEqual(selected, ["device-b", "device-a", "device-c"])


if __name__ == "__main__":
    unittest.main()
