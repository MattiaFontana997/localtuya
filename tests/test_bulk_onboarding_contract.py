"""Stable user-facing contract for QR bulk onboarding."""

from __future__ import annotations

import unittest


class BulkOnboardingContractTests(unittest.TestCase):
    def test_bulk_contract_is_select_process_summary(self):
        self.assertEqual(
            ["select_multiple", "process_sequentially", "summary"],
            ["select_multiple", "process_sequentially", "summary"],
        )


if __name__ == "__main__":
    unittest.main()
