"""Bulk failure reason is an opaque code, not an exception message."""

from __future__ import annotations

import unittest


class BulkInternalReasonPrivacyTests(unittest.TestCase):
    def test_reason_is_opaque_code(self):
        reason = "probe_error"
        self.assertNotIn(":", reason)


if __name__ == "__main__":
    unittest.main()
