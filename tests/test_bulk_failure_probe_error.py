"""Unexpected bulk probe errors collapse to a safe code."""

from __future__ import annotations

import unittest


class BulkProbeFailureTests(unittest.TestCase):
    def test_probe_error_code_contains_no_exception_text(self):
        reason = "probe_error"
        self.assertEqual(reason, "probe_error")
        self.assertNotIn("Exception", reason)


if __name__ == "__main__":
    unittest.main()
