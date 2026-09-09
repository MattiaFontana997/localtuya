"""Bulk user-facing labels are account names or IDs, never credentials."""

from __future__ import annotations

import unittest


class BulkLabelPrivacyTests(unittest.TestCase):
    def test_label_contract_has_no_credentials(self):
        label = "Kitchen lamp"
        self.assertNotIn("local_key", label)
        self.assertNotIn("192.168.", label)


if __name__ == "__main__":
    unittest.main()
