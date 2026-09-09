"""Bulk mode field remains stable for future flow migrations."""

from __future__ import annotations

import unittest

from custom_components.localtuya.qr_onboarding import CONF_QR_BULK_MODE


class BulkModeConstantTests(unittest.TestCase):
    def test_bulk_mode_constant_is_stable(self):
        self.assertEqual(CONF_QR_BULK_MODE, "qr_bulk_mode")


if __name__ == "__main__":
    unittest.main()
