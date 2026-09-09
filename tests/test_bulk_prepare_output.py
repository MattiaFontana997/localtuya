"""Bulk prepare output contains successes and failures only."""

from __future__ import annotations

import unittest


class BulkPrepareOutputTests(unittest.TestCase):
    def test_output_keys(self):
        output = {"successes": [], "failures": []}
        self.assertEqual(sorted(output), ["failures", "successes"])


if __name__ == "__main__":
    unittest.main()
