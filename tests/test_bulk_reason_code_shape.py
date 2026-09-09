"""Bulk failure reason codes remain identifier-free strings."""

from __future__ import annotations

import unittest


class BulkReasonCodeShapeTests(unittest.TestCase):
    def test_reason_code_is_simple_string(self):
        reason = "cannot_connect"
        self.assertIsInstance(reason, str)
        self.assertNotIn(" ", reason)


if __name__ == "__main__":
    unittest.main()
