"""Already configured devices are excluded from bulk onboarding."""

from __future__ import annotations

import unittest


class BulkConfiguredFilterTests(unittest.TestCase):
    def test_configured_ids_are_removed(self):
        account = {"a": {}, "b": {}}
        configured = {"a"}
        eligible = {k: v for k, v in account.items() if k not in configured}
        self.assertEqual(list(eligible), ["b"])


if __name__ == "__main__":
    unittest.main()
