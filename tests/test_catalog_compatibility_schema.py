"""Compatibility metadata schema tests for catalog validation."""

from __future__ import annotations

import unittest

from custom_components.localtuya.device_catalog import DeviceCatalog


class CatalogCompatibilitySchemaTests(unittest.TestCase):
    def test_compatibility_metadata_survives_validation(self):
        raw = {
            "schema_version": 2,
            "mappings": [
                {
                    "id": "map-1",
                    "confidence": "verified",
                    "match": {
                        "product_ids": ["prod-1"],
                        "category": "dj",
                        "required_dps": [20],
                        "optional_dps": [],
                    },
                    "compatibility": {
                        "hardware_tested": True,
                        "protocols": ["3.5"],
                        "transport": "direct",
                        "home_assistant": "2026.9",
                        "localtuya": "6.7.0-dev",
                        "tested_at": "2026-09-09",
                    },
                    "entities": [
                        {"platform": "switch", "config": {"id": 20, "platform": "switch"}}
                    ],
                }
            ],
        }
        catalog = DeviceCatalog.__new__(DeviceCatalog)
        normalized = catalog._validate_catalog(raw)
        self.assertEqual(normalized["mappings"][0]["compatibility"]["protocols"], ["3.5"])

    def test_invalid_transport_rejects_mapping(self):
        raw = {
            "schema_version": 2,
            "mappings": [
                {
                    "id": "map-1",
                    "confidence": "verified",
                    "match": {"product_ids": ["prod-1"], "required_dps": [20]},
                    "compatibility": {"hardware_tested": True, "protocols": ["3.5"], "transport": "magic"},
                    "entities": [{"platform": "switch", "config": {"id": 20, "platform": "switch"}}],
                }
            ],
        }
        catalog = DeviceCatalog.__new__(DeviceCatalog)
        normalized = catalog._validate_catalog(raw)
        self.assertEqual(normalized["mappings"], [])


if __name__ == "__main__":
    unittest.main()
