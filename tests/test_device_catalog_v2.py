"""Tests for LocalTuya device catalog schema v2 runtime behaviour."""

import unittest

from custom_components.localtuya.device_catalog import (
    match_catalog_mapping,
    validate_catalog,
)


def v2_mapping(
    mapping_id="device-v2",
    *,
    product_ids=None,
    required_dps=None,
    optional_dps=None,
    entities=None,
    provenance=None,
):
    if product_ids is None:
        product_ids = ["alias-a", "product-a"]
    if required_dps is None:
        required_dps = [1]
    if optional_dps is None:
        optional_dps = []
    if entities is None:
        entities = [
            {
                "platform": "switch",
                "config": {
                    "id": 1,
                    "platform": "switch",
                },
            }
        ]

    mapping = {
        "id": mapping_id,
        "confidence": "experimental",
        "match": {
            "product_ids": product_ids,
            "category": "kg",
            "required_dps": required_dps,
            "optional_dps": optional_dps,
        },
        "entities": entities,
    }
    if provenance is not None:
        mapping["provenance"] = provenance
    return mapping


def payload(*mappings):
    return {
        "schema_version": 2,
        "mappings": list(mappings),
    }


class TestDeviceCatalogV2(unittest.TestCase):
    def test_v1_is_normalized_to_v2(self):
        result = validate_catalog(
            {
                "schema_version": 1,
                "mappings": [
                    {
                        "id": "legacy",
                        "match": {
                            "product_id": "legacy-product",
                            "required_dps": [],
                        },
                        "entities": [
                            {
                                "platform": "switch",
                                "config": {"id": 1, "platform": "switch"},
                            }
                        ],
                    }
                ],
            }
        )

        self.assertEqual(result["schema_version"], 2)
        match = result["mappings"][0]["match"]
        self.assertEqual(match["product_ids"], ["legacy-product"])
        self.assertEqual(match["required_dps"], [1])
        self.assertEqual(match["optional_dps"], [])

    def test_product_alias_matches_same_mapping(self):
        catalog = validate_catalog(payload(v2_mapping()))

        result = match_catalog_mapping(
            catalog,
            {"product_id": "alias-a", "category": "kg"},
            {1},
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.mapping_id, "device-v2")
        self.assertEqual(result.product_id, "alias-a")
        self.assertEqual(result.product_ids, ("alias-a", "product-a"))

    def test_absent_optional_secondary_dp_is_pruned(self):
        catalog = validate_catalog(
            payload(
                v2_mapping(
                    optional_dps=[18],
                    entities=[
                        {
                            "platform": "switch",
                            "config": {
                                "id": 1,
                                "platform": "switch",
                                "current_consumption": 18,
                            },
                        }
                    ],
                )
            )
        )

        result = match_catalog_mapping(
            catalog,
            {"product_id": "product-a", "category": "kg"},
            {1},
        )

        self.assertIsNotNone(result)
        self.assertNotIn("current_consumption", result.entities[0]["config"])
        self.assertEqual(result.optional_dps, (18,))

    def test_present_optional_secondary_dp_is_kept(self):
        catalog = validate_catalog(
            payload(
                v2_mapping(
                    optional_dps=[18],
                    entities=[
                        {
                            "platform": "switch",
                            "config": {
                                "id": 1,
                                "platform": "switch",
                                "current_consumption": 18,
                            },
                        }
                    ],
                )
            )
        )

        result = match_catalog_mapping(
            catalog,
            {"product_id": "product-a", "category": "kg"},
            {1, 18},
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.entities[0]["config"]["current_consumption"], 18)

    def test_optional_primary_dp_skips_only_that_entity(self):
        catalog = validate_catalog(
            payload(
                v2_mapping(
                    required_dps=[1],
                    optional_dps=[18],
                    entities=[
                        {
                            "platform": "switch",
                            "config": {"id": 1, "platform": "switch"},
                        },
                        {
                            "platform": "sensor",
                            "config": {"id": 18, "platform": "sensor"},
                        },
                    ],
                )
            )
        )

        result = match_catalog_mapping(
            catalog,
            {"product_id": "product-a", "category": "kg"},
            {1},
        )

        self.assertIsNotNone(result)
        self.assertEqual(len(result.entities), 1)
        self.assertEqual(result.entities[0]["platform"], "switch")

    def test_undeclared_v2_dp_reference_rejects_mapping(self):
        catalog = validate_catalog(
            payload(
                v2_mapping(
                    entities=[
                        {
                            "platform": "switch",
                            "config": {
                                "id": 1,
                                "platform": "switch",
                                "current_consumption": 18,
                            },
                        }
                    ]
                )
            )
        )
        self.assertEqual(catalog["mappings"], [])

    def test_provenance_is_preserved(self):
        provenance = {
            "source": "make-all/tuya-local",
            "path": "custom_components/tuya_local/devices/example.yaml",
            "revision": "deadbeef",
            "license": "MIT",
        }
        catalog = validate_catalog(payload(v2_mapping(provenance=provenance)))
        result = match_catalog_mapping(
            catalog,
            {"product_id": "product-a", "category": "kg"},
            {1},
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.provenance, provenance)


if __name__ == "__main__":
    unittest.main()
