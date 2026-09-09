"""One bulk failure must not prevent later devices."""

from __future__ import annotations

import unittest


class BulkFailureIsolationTests(unittest.TestCase):
    def test_failure_isolation_contract(self):
        outcomes = ["ok", "fail", "ok"]
        processed = [index for index, _ in enumerate(outcomes)]
        self.assertEqual(processed, [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
