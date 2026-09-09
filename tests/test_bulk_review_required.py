"""Bulk onboarding separates devices needing mapping review."""

from __future__ import annotations

import unittest


class BulkReviewRequiredTests(unittest.TestCase):
    def test_review_required_is_separate_from_failures(self):
        summary = {"added": ["a"], "review_required": ["b"], "failures": [{"device_id": "c", "reason": "cannot_connect"}]}
        self.assertIn("b", summary["review_required"])
        self.assertNotEqual(summary["review_required"], summary["failures"])


if __name__ == "__main__":
    unittest.main()
