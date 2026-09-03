"""Regression tests for the unified LocalTuya device catalog."""

import unittest
from types import SimpleNamespace

from custom_components.localtuya.config_flow import (
    async_get_entity_candidates,
)
from custom_components.localtuya.const import (
    DATA_DEVICE_CATALOG,
    DOMAIN,
)
from custom_components.localtuya.device_catalog import (
    DeviceCatalog,
    load_builtin_catalog,
    match_catalog_mapping,
)
from custom_components.localtuya.mapping_resolver import (
    resolve_entity_candidates,
)


PRODUCT_ID = "wxmbjwpt8yea7bag"

DEVICE_ID = "catalog-test-device"

OBSERVED_DPS = {
    1,
    2,
    16,
    24,
    32,
    33,
    103,
}


SPECIFICATION = {
    "functions": [
        {
            "dp_id": 1,
            "code": "switch",
            "type": "Boolean",
            "values": "{}",
        },
        {
            "dp_id": 2,
            "code": "mode",
            "type": "Enum",
            "values": (
                '{"range":'
                '["auto","manual","holiday"]}'
            ),
        },
        {
            "dp_id": 16,
            "code": "temp_set",
            "type": "Integer",
            "values": (
                '{"unit":"℃","min":50,'
                '"max":350,"scale":1,'
                '"step":5}'
            ),
        },
    ],
    "status": [
        {
            "dp_id": 1,
            "code": "switch",
            "type": "Boolean",
            "values": "{}",
        },
        {
            "dp_id": 2,
            "code": "mode",
            "type": "Enum",
            "values": (
                '{"range":'
                '["auto","manual","holiday"]}'
            ),
        },
        {
            "dp_id": 16,
            "code": "temp_set",
            "type": "Integer",
            "values": (
                '{"unit":"℃","min":50,'
                '"max":350,"scale":1,'
                '"step":5}'
            ),
        },
        {
            "dp_id": 24,
            "code": "temp_current",
            "type": "Integer",
            "values": (
                '{"unit":"℃","min":0,'
                '"max":400,"scale":1,'
                '"step":1}'
            ),
        },
    ],
}


class BundledOnlyCatalog:
    """Expose only LocalTuya's bundled catalog."""

    def __init__(self):
        self.catalog = (
            load_builtin_catalog()
        )

    def match(
        self,
        device,
        available_dps,
    ):
        return match_catalog_mapping(
            self.catalog,
            device,
            available_dps,
            source="bundled",
        )


class UnifiedCatalogTests(
    unittest.IsolatedAsyncioTestCase
):
    """Test bundled, remote and no-Cloud resolution."""

    def test_snapshot_contains_only_verified(
        self,
    ):
        catalog = (
            load_builtin_catalog()
        )

        self.assertGreater(
            len(
                catalog["mappings"]
            ),
            0,
        )

        self.assertTrue(
            all(
                mapping["confidence"]
                == "verified"
                for mapping
                in catalog["mappings"]
            )
        )

    def test_match_without_category(
        self,
    ):
        match = (
            match_catalog_mapping(
                load_builtin_catalog(),
                {
                    "product_key":
                        PRODUCT_ID,
                },
                OBSERVED_DPS,
                source="bundled",
            )
        )

        self.assertIsNotNone(
            match
        )

        self.assertEqual(
            match.mapping_id,
            (
                "wxmbjwpt8yea7bag-"
                "ef945de926"
            ),
        )

        self.assertEqual(
            match.source,
            "bundled",
        )

    def test_verified_bundled_beats_experimental_remote(
        self,
    ):
        catalog = object.__new__(
            DeviceCatalog
        )

        catalog._builtin_catalog = (
            load_builtin_catalog()
        )

        catalog._catalog = {
            "schema_version": 1,
            "mappings": [
                {
                    "id":
                        "experimental-remote",
                    "confidence":
                        "experimental",
                    "match": {
                        "product_id":
                            PRODUCT_ID,
                        "category":
                            "wk",
                        "required_dps": [
                            1,
                        ],
                    },
                    "entities": [
                        {
                            "platform":
                                "climate",
                            "config": {
                                "id": 1,
                                "platform":
                                    "climate",
                            },
                        }
                    ],
                }
            ],
        }

        match = catalog.match(
            {
                "product_id":
                    PRODUCT_ID,
                "category":
                    "wk",
            },
            OBSERVED_DPS,
        )

        self.assertIsNotNone(
            match
        )

        self.assertEqual(
            match.confidence,
            "verified",
        )

        self.assertEqual(
            match.source,
            "bundled",
        )

    def test_bundled_enriches_generic_mapper(
        self,
    ):
        candidates = (
            resolve_entity_candidates(
                {
                    "name":
                        "Termostato",
                    "category":
                        "wk",
                    "product_id":
                        PRODUCT_ID,
                },
                SPECIFICATION,
                OBSERVED_DPS,
                catalog_client=(
                    BundledOnlyCatalog()
                ),
            )
        )

        climate = next(
            candidate
            for candidate
            in candidates
            if (
                candidate.platform
                == "climate"
            )
        )

        self.assertEqual(
            climate.confidence.value,
            "high",
        )

        self.assertEqual(
            climate.config[
                "preset_set"
            ],
            (
                "auto/manual/temporary/"
                "boost/holiday"
            ),
        )

        self.assertEqual(
            climate.config[
                "hvac_mode_dp"
            ],
            103,
        )

        self.assertEqual(
            climate.config[
                "away_temperature_dp"
            ],
            32,
        )

        numbers = {
            candidate.primary_dp:
                candidate
            for candidate
            in candidates
            if (
                candidate.platform
                == "number"
            )
        }

        self.assertIn(
            32,
            numbers,
        )

        self.assertIn(
            33,
            numbers,
        )

        self.assertEqual(
            numbers[32].confidence.value,
            "high",
        )

        self.assertEqual(
            numbers[33].confidence.value,
            "high",
        )

    async def test_config_flow_catalog_works_without_cloud(
        self,
    ):
        hass = SimpleNamespace(
            data={
                DOMAIN: {
                    DATA_DEVICE_CATALOG:
                        BundledOnlyCatalog(),
                }
            }
        )

        candidates = (
            await async_get_entity_candidates(
                hass,
                {
                    "device_id":
                        DEVICE_ID,
                    "friendly_name":
                        "Termostato Offline",
                },
                {
                    DEVICE_ID: {
                        "gwId":
                            DEVICE_ID,
                        "productKey":
                            PRODUCT_ID,
                        "category":
                            "wk",
                    }
                },
                [
                    "1 (value: True)",
                    "2 (value: manual)",
                    "16 (value: 205)",
                    "24 (value: 267)",
                    "32 (value: 210)",
                    "33 (value: 9)",
                    (
                        "103 "
                        "(value: heatcool_cool)"
                    ),
                ],
            )
        )

        self.assertEqual(
            len(candidates),
            3,
        )

        self.assertTrue(
            all(
                candidate.confidence.value
                == "high"
                for candidate
                in candidates
            )
        )


if __name__ == "__main__":
    unittest.main()
