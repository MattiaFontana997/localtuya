"""Compatibility generator remains product-level only."""

from __future__ import annotations

import unittest


class CompatibilityGeneratorPrivacyTests(unittest.TestCase):
    def test_private_columns_are_not_part_of_public_table_contract(self):
        columns = {"product_id", "category", "protocol", "transport", "mapping_id", "status", "home_assistant", "localtuya", "tested_at"}
        for forbidden in {"device_id", "host", "local_key", "mac", "account_id"}:
            self.assertNotIn(forbidden, columns)


if __name__ == "__main__":
    unittest.main()
