"""Multiple tested protocols create distinct compatibility rows."""

from __future__ import annotations

import unittest

from custom_components.localtuya.compatibility_matrix import records_from_catalog


class CompatibilityMultipleProtocolsTests(unittest.TestCase):
    def test_multiple_protocols_create_multiple_records(self):
        records = records_from_catalog({"mappings": [{
            "id": "m", "confidence": "verified",
            "match": {"product_ids": ["p"], "category": "dj"},
            "compatibility": {"hardware_tested": True, "protocols": ["3.4", "3.5"], "transport": "direct"},
        }]})
        self.assertEqual([r.protocol for r in records], ["3.4", "3.5"])


if __name__ == "__main__":
    unittest.main()
