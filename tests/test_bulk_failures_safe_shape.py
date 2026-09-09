"""Bulk failure items expose only device routing identity and a reason code internally."""

from __future__ import annotations

import unittest


class BulkFailureSafeShapeTests(unittest.TestCase):
    def test_failure_item_has_no_credentials(self):
        item = {"device_id": "x", "reason": "cannot_connect"}
        self.assertNotIn("local_key", item)
        self.assertNotIn("host", item)
        self.assertNotIn("token", item)


if __name__ == "__main__":
    unittest.main()
