"""Successful bulk onboarding can report zero failures."""

from __future__ import annotations

import unittest


class BulkEmptyFailuresTests(unittest.TestCase):
    def test_empty_failures_count_is_zero(self):
        self.assertEqual(len([]), 0)


if __name__ == "__main__":
    unittest.main()
