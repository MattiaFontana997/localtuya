"""Compatibility metadata protocol-list extraction."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import records_from_catalog


class CompatibilityProtocolExtractionTests(unittest.TestCase):
    def test_protocol_string_is_normalized_to_one_record(self):
        records = records_from_catalog({"mappings": [{
            "id": "m", "confidence": "community",
            "match": {"product_ids": ["p"], "category": "dj"},
            "compatibility": {"hardware_tested": True, "protocols": "3.5", "transport": "direct"},
        }]})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].protocol, "3.5")


if __name__ == "__main__":
    unittest.main()
