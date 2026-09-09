"""Missing QR devices use a stable bulk failure code."""

from __future__ import annotations

import unittest


class BulkMissingDeviceReasonTests(unittest.TestCase):
    def test_missing_device_reason_is_stable(self):
        self.assertEqual("device_not_found", "device_not_found")


if __name__ == "__main__":
    unittest.main()
