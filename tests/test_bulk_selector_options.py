"""Bulk selector options use value/label pairs."""

from __future__ import annotations

import unittest


class BulkSelectorOptionsTests(unittest.TestCase):
    def test_option_shape(self):
        option = {"value": "id", "label": "Lamp"}
        self.assertEqual(set(option), {"value", "label"})


if __name__ == "__main__":
    unittest.main()
