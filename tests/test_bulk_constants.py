"""Bulk onboarding field names remain stable."""

from __future__ import annotations

import unittest

from custom_components.localtuya.qr_onboarding import CONF_QR_BULK_DEVICE_IDS


class BulkConstantsTests(unittest.TestCase):
    def test_bulk_device_ids_field_is_stable(self):
        self.assertEqual(CONF_QR_BULK_DEVICE_IDS, "qr_bulk_device_ids")


if __name__ == "__main__":
    unittest.main()
