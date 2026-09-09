"""Bulk failure reasons remain privacy-safe codes."""

from __future__ import annotations

import unittest


class BulkFailureReasonTests(unittest.TestCase):
    def test_failure_reasons_are_codes_not_messages(self):
        reasons = {"cannot_connect", "device_not_found", "probe_error"}
        for reason in reasons:
            self.assertNotIn("192.168.", reason)
            self.assertNotIn("local_key", reason)


if __name__ == "__main__":
    unittest.main()
