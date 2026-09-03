"""Tests for LocalTuya remote device catalog."""

import unittest

from custom_components.localtuya.device_catalog import (
    match_catalog_mapping,
    validate_catalog,
)


class TestDeviceCatalog(unittest.TestCase):
    """Tests for remote catalog validation and matching."""

    def test_valid_catalog(self):
        payload = {
            "schema_version": 1,
            "mappings": [
                {
                    "id": "test-product",
                    "confidence": "verified",
                    "match": {
                        "product_id": "abc123",
                        "category": "cz",
                        "required_dps": [1, 18],
                    },
                    "entities": [
                        {
                            "platform": "switch",
                            "config": {
                                "id": 1,
                                "friendly_name": "Plug",
                                "platform": "switch",
                            },
                        }
                    ],
                }
            ],
        }

        catalog = validate_catalog(payload)

        self.assertEqual(len(catalog["mappings"]), 1)
        self.assertEqual(
            catalog["mappings"][0]["id"],
            "test-product",
        )

    def test_product_and_dps_match(self):
        catalog = validate_catalog(
            {
                "schema_version": 1,
                "mappings": [
                    {
                        "id": "plug",
                        "confidence": "verified",
                        "match": {
                            "product_id": "abc123",
                            "category": "cz",
                            "required_dps": [1, 18],
                        },
                        "entities": [
                            {
                                "platform": "switch",
                                "config": {
                                    "id": 1,
                                    "platform": "switch",
                                },
                            }
                        ],
                    }
                ],
            }
        )

        result = match_catalog_mapping(
            catalog,
            {
                "product_id": "abc123",
                "category": "cz",
            },
            {1, 18, 19, 20},
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.mapping_id, "plug")
        self.assertEqual(result.confidence, "verified")

    def test_missing_required_dp_rejected(self):
        catalog = validate_catalog(
            {
                "schema_version": 1,
                "mappings": [
                    {
                        "id": "plug",
                        "confidence": "verified",
                        "match": {
                            "product_id": "abc123",
                            "required_dps": [1, 18],
                        },
                        "entities": [
                            {
                                "platform": "switch",
                                "config": {
                                    "id": 1,
                                    "platform": "switch",
                                },
                            }
                        ],
                    }
                ],
            }
        )

        result = match_catalog_mapping(
            catalog,
            {"product_id": "abc123"},
            {1},
        )

        self.assertIsNone(result)

    def test_wrong_product_rejected(self):
        catalog = validate_catalog(
            {
                "schema_version": 1,
                "mappings": [
                    {
                        "id": "plug",
                        "match": {
                            "product_id": "abc123",
                        },
                        "entities": [
                            {
                                "platform": "switch",
                                "config": {
                                    "id": 1,
                                    "platform": "switch",
                                },
                            }
                        ],
                    }
                ],
            }
        )

        result = match_catalog_mapping(
            catalog,
            {"product_id": "different"},
            {1},
        )

        self.assertIsNone(result)

    def test_invalid_platform_removed(self):
        catalog = validate_catalog(
            {
                "schema_version": 1,
                "mappings": [
                    {
                        "id": "bad",
                        "match": {
                            "product_id": "abc",
                        },
                        "entities": [
                            {
                                "platform": "python",
                                "config": {
                                    "id": 1,
                                },
                            }
                        ],
                    }
                ],
            }
        )

        self.assertEqual(
            catalog["mappings"],
            [],
        )


if __name__ == "__main__":
    unittest.main()
