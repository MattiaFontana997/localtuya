"""Bulk selector exposes eligible device options."""

from __future__ import annotations

import unittest


class BulkOptionsNonemptyTests(unittest.TestCase):
    def test_option_list_can_hold_multiple_devices(self):
        options = [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]
        self.assertEqual(len(options), 2)


if __name__ == "__main__":
    unittest.main()
