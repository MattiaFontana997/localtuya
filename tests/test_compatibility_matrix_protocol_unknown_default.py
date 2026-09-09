"""Missing compatibility protocol evidence normalizes to unknown."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import records_from_catalog


class CompatibilityUnknownDefaultTests(unittest.TestCase):
    def test_missing_protocols_defaults_to_unknown(self):
        records = records_from_catalog({"mappings": [{
            "id": "m", "confidence": "community",
            "match": {"product_ids": ["p"]},
            "compatibility": {"hardware_tested": True, "transport": "direct"},
        }]})
        self.assertEqual(records[0].protocol, "unknown")


if __name__ == "__main__":
    unittest.main()
