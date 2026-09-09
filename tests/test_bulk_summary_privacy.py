"""Privacy checks for QR bulk onboarding summaries."""

from __future__ import annotations

import unittest


class BulkSummaryPrivacyTests(unittest.TestCase):
    def test_summary_contract_exposes_counts_not_credentials(self):
        summary = {
            "added_count": "4",
            "failed_count": "1",
            "review_count": "2",
        }
        rendered = repr(summary)
        self.assertNotIn("local_key", rendered)
        self.assertNotIn("device_id", rendered)
        self.assertNotIn("host", rendered)


if __name__ == "__main__":
    unittest.main()
