"""Persistent remote catalog tests."""

import unittest

from custom_components.localtuya.device_catalog import (
    DeviceCatalog,
    validate_catalog,
)


class FakeStore:
    """Minimal Home Assistant Store replacement."""

    def __init__(self, data=None):
        self.data = data
        self.saved = None

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.saved = data


class TestDeviceCatalogCache(
    unittest.IsolatedAsyncioTestCase
):
    """Catalog cache tests."""

    async def test_valid_cached_catalog_is_restored(
        self,
    ):
        url = (
            "https://example.invalid/"
            "catalog.json"
        )

        cached = {
            "url": url,
            "etag": '"test-etag"',
            "catalog": {
                "schema_version": 1,
                "mappings": [
                    {
                        "id": "plug-test",
                        "confidence": "verified",
                        "match": {
                            "product_id": "abc123",
                            "category": "cz",
                            "required_dps": [1],
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
            },
        }

        catalog = DeviceCatalog(
            None,
            url=url,
            session=object(),
            store=FakeStore(cached),
        )

        result = (
            await catalog.async_load_cache()
        )

        self.assertTrue(result)
        self.assertTrue(
            catalog.cache_loaded
        )
        self.assertEqual(
            catalog.mapping_count,
            1,
        )

        match = catalog.match(
            {
                "product_id": "abc123",
                "category": "cz",
            },
            {1},
        )

        self.assertIsNotNone(match)
        self.assertEqual(
            match.mapping_id,
            "plug-test",
        )


class TestDeviceCatalogSafety(
    unittest.TestCase
):
    """Remote catalog safety tests."""

    def test_entity_with_private_config_is_rejected(
        self,
    ):
        catalog = validate_catalog(
            {
                "schema_version": 1,
                "mappings": [
                    {
                        "id": "unsafe",
                        "match": {
                            "product_id": "abc123",
                            "required_dps": [1],
                        },
                        "entities": [
                            {
                                "platform": "switch",
                                "config": {
                                    "id": 1,
                                    "platform": "switch",
                                    "local_key": "do-not-accept",
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
