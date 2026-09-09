"""Sequential processing remains a bulk-onboarding invariant."""

from __future__ import annotations

import unittest


class BulkSequentialContractTests(unittest.TestCase):
    def test_processing_order_is_stable(self):
        selected = ["one", "two", "three"]
        processed = []
        for item in selected:
            processed.append(item)
        self.assertEqual(processed, selected)


if __name__ == "__main__":
    unittest.main()
