"""Security and corruption hardening tests for the device catalog."""

from __future__ import annotations

import unittest

from custom_components.localtuya.device_catalog import (
    DeviceCatalog,
    validate_catalog,
)


def mapping(
    mapping_id="test",
    *,
    confidence="verified",
    product_id="abc123",
    category="cz",
    required_dps=None,
    entities=None,
):
    """Build a minimal catalog mapping."""
    if required_dps is None:
        required_dps = [1]

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

    return {
        "id": mapping_id,
        "confidence": confidence,
        "match": {
            "product_id": product_id,
            "category": category,
            "required_dps": required_dps,
        },
        "entities": entities,
    }


def catalog_payload(*mappings):
    """Build a schema-v1 catalog."""
    return {
        "schema_version": 1,
        "mappings": list(mappings),
    }


class FakeStore:
    """Minimal HA Store replacement."""

    def __init__(self, data=None):
        self.data = data
        self.saved = None

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.saved = data


class FakeResponse:
    """Minimal aiohttp response replacement."""

    def __init__(
        self,
        payload,
        *,
        content_length=None,
    ):
        self.status = 200
        self.headers = {}
        self.content_length = content_length
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        return False

    async def json(
        self,
        *,
        content_type=None,
    ):
        return self._payload


class FakeSession:
    """Minimal aiohttp ClientSession replacement."""

    def __init__(self, response):
        self.response = response

    def get(
        self,
        url,
        *,
        headers,
        timeout,
    ):
        return self.response


class TestCatalogStructuralHardening(
    unittest.TestCase
):
    """Validate fail-closed catalog behaviour."""

    def test_duplicate_mapping_ids_reject_catalog(
        self,
    ):
        payload = catalog_payload(
            mapping("duplicate"),
            mapping(
                "duplicate",
                product_id="different",
            ),
        )

        with self.assertRaises(ValueError):
            validate_catalog(payload)

    def test_unknown_confidence_rejects_mapping(
        self,
    ):
        result = validate_catalog(
            catalog_payload(
                mapping(
                    confidence="super-trusted",
                )
            )
        )

        self.assertEqual(
            result["mappings"],
            [],
        )

    def test_mapping_is_atomic_when_entity_is_invalid(
        self,
    ):
        entities = [
            {
                "platform": "switch",
                "config": {
                    "id": 1,
                    "platform": "switch",
                },
            },
            {
                "platform": "python",
                "config": {
                    "id": 2,
                },
            },
        ]

        result = validate_catalog(
            catalog_payload(
                mapping(
                    entities=entities,
                )
            )
        )

        self.assertEqual(
            result["mappings"],
            [],
        )

    def test_non_string_category_is_rejected(
        self,
    ):
        result = validate_catalog(
            catalog_payload(
                mapping(
                    category={
                        "unexpected": True,
                    }
                )
            )
        )

        self.assertEqual(
            result["mappings"],
            [],
        )

    def test_out_of_range_dp_is_rejected(
        self,
    ):
        result = validate_catalog(
            catalog_payload(
                mapping(
                    required_dps=[
                        1,
                        65536,
                    ]
                )
            )
        )

        self.assertEqual(
            result["mappings"],
            [],
        )

    def test_sensitive_camel_case_key_is_rejected(
        self,
    ):
        entities = [
            {
                "platform": "switch",
                "config": {
                    "id": 1,
                    "platform": "switch",
                    "localKey":
                        "must-not-be-accepted",
                },
            }
        ]

        result = validate_catalog(
            catalog_payload(
                mapping(
                    entities=entities,
                )
            )
        )

        self.assertEqual(
            result["mappings"],
            [],
        )

    def test_excessive_mapping_count_is_rejected(
        self,
    ):
        payload = catalog_payload(
            *(
                mapping(
                    f"mapping-{index}",
                    product_id=f"product-{index}",
                )
                for index in range(2049)
            )
        )

        with self.assertRaises(ValueError):
            validate_catalog(payload)

    def test_excessively_nested_config_is_rejected(
        self,
    ):
        nested = "value"

        for _ in range(20):
            nested = {
                "nested": nested,
            }

        entities = [
            {
                "platform": "switch",
                "config": {
                    "id": 1,
                    "platform": "switch",
                    "metadata": nested,
                },
            }
        ]

        result = validate_catalog(
            catalog_payload(
                mapping(
                    entities=entities,
                )
            )
        )

        self.assertEqual(
            result["mappings"],
            [],
        )


class TestCatalogRuntimeHardening(
    unittest.IsolatedAsyncioTestCase
):
    """Validate cache and remote-download hardening."""

    async def test_cache_from_different_url_is_ignored(
        self,
    ):
        cached = {
            "url":
                "https://old.example/catalog.json",
            "etag": '"old"',
            "catalog": catalog_payload(
                mapping()
            ),
        }

        device_catalog = DeviceCatalog(
            None,
            url=(
                "https://new.example/"
                "catalog.json"
            ),
            session=object(),
            store=FakeStore(cached),
        )

        result = (
            await device_catalog.async_load_cache()
        )

        self.assertFalse(result)
        self.assertFalse(
            device_catalog.cache_loaded
        )

    async def test_oversized_remote_catalog_is_rejected(
        self,
    ):
        store = FakeStore()

        response = FakeResponse(
            catalog_payload(
                mapping()
            ),
            content_length=(
                3 * 1024 * 1024
            ),
        )

        device_catalog = DeviceCatalog(
            None,
            url=(
                "https://example.invalid/"
                "catalog.json"
            ),
            session=FakeSession(response),
            store=store,
        )

        result = (
            await device_catalog.async_refresh()
        )

        self.assertFalse(result)
        self.assertIsNone(
            device_catalog.catalog
        )
        self.assertIsNone(
            store.saved
        )


if __name__ == "__main__":
    unittest.main()


class FakeStatusResponse(FakeResponse):
    """Fake response with configurable HTTP status."""

    def __init__(
        self,
        payload=None,
        *,
        status=200,
        headers=None,
        content_length=None,
    ):
        super().__init__(
            payload,
            content_length=content_length,
        )
        self.status = status
        self.headers = (
            headers
            if headers is not None
            else {}
        )


class TestCatalogRefreshIntegrity(
    unittest.IsolatedAsyncioTestCase
):
    """Ensure failed/corrupt refreshes never replace good state."""

    async def test_invalid_remote_catalog_preserves_current(
        self,
    ):
        valid = validate_catalog(
            catalog_payload(
                mapping(
                    "current-good",
                )
            )
        )

        invalid_remote = catalog_payload(
            mapping(
                "remote-bad",
                entities=[
                    {
                        "platform": "python",
                        "config": {
                            "id": 1,
                        },
                    }
                ],
            )
        )

        device_catalog = DeviceCatalog(
            None,
            url=(
                "https://example.invalid/"
                "catalog.json"
            ),
            session=FakeSession(
                FakeStatusResponse(
                    invalid_remote
                )
            ),
            store=FakeStore(),
        )

        device_catalog._catalog = valid
        device_catalog._etag = '"old-etag"'

        result = (
            await device_catalog.async_refresh()
        )

        self.assertFalse(result)

        self.assertEqual(
            device_catalog.catalog,
            valid,
        )

        self.assertEqual(
            device_catalog._etag,
            '"old-etag"',
        )

    async def test_invalid_cached_mapping_is_ignored(
        self,
    ):
        url = (
            "https://example.invalid/"
            "catalog.json"
        )

        cached = {
            "url": url,
            "etag": '"bad-cache"',
            "catalog": catalog_payload(
                mapping(
                    "bad-cache-entry",
                    entities=[
                        {
                            "platform":
                                "python",
                            "config": {
                                "id": 1,
                            },
                        }
                    ],
                )
            ),
        }

        device_catalog = DeviceCatalog(
            None,
            url=url,
            session=object(),
            store=FakeStore(cached),
        )

        result = (
            await device_catalog.async_load_cache()
        )

        self.assertFalse(result)
        self.assertFalse(
            device_catalog.cache_loaded
        )
        self.assertIsNone(
            device_catalog.catalog
        )

    async def test_http_error_preserves_current_catalog(
        self,
    ):
        valid = validate_catalog(
            catalog_payload(
                mapping(
                    "current-good",
                )
            )
        )

        device_catalog = DeviceCatalog(
            None,
            url=(
                "https://example.invalid/"
                "catalog.json"
            ),
            session=FakeSession(
                FakeStatusResponse(
                    status=503
                )
            ),
            store=FakeStore(),
        )

        device_catalog._catalog = valid

        result = (
            await device_catalog.async_refresh()
        )

        self.assertFalse(result)
        self.assertEqual(
            device_catalog.catalog,
            valid,
        )

    async def test_304_without_catalog_is_not_success(
        self,
    ):
        device_catalog = DeviceCatalog(
            None,
            url=(
                "https://example.invalid/"
                "catalog.json"
            ),
            session=FakeSession(
                FakeStatusResponse(
                    status=304
                )
            ),
            store=FakeStore(),
        )

        result = (
            await device_catalog.async_refresh()
        )

        self.assertFalse(result)

    async def test_304_with_catalog_preserves_catalog(
        self,
    ):
        valid = validate_catalog(
            catalog_payload(
                mapping(
                    "current-good",
                )
            )
        )

        device_catalog = DeviceCatalog(
            None,
            url=(
                "https://example.invalid/"
                "catalog.json"
            ),
            session=FakeSession(
                FakeStatusResponse(
                    status=304
                )
            ),
            store=FakeStore(),
        )

        device_catalog._catalog = valid

        result = (
            await device_catalog.async_refresh()
        )

        self.assertTrue(result)
        self.assertEqual(
            device_catalog.catalog,
            valid,
        )


class TestCatalogTrustHardening(
    unittest.TestCase
):
    """Ensure remote knowledge cannot reduce bundled trust."""

    def _client_with(
        self,
        remote_confidence,
        bundled_confidence,
    ):
        device_catalog = object.__new__(
            DeviceCatalog
        )

        device_catalog._catalog = (
            validate_catalog(
                catalog_payload(
                    mapping(
                        "remote",
                        confidence=(
                            remote_confidence
                        ),
                    )
                )
            )
        )

        device_catalog._builtin_catalog = (
            validate_catalog(
                catalog_payload(
                    mapping(
                        "bundled",
                        confidence=(
                            bundled_confidence
                        ),
                    )
                )
            )
        )

        return device_catalog

    def test_community_remote_cannot_replace_verified_bundled(
        self,
    ):
        device_catalog = self._client_with(
            "community",
            "verified",
        )

        result = device_catalog.match(
            {
                "product_id": "abc123",
                "category": "cz",
            },
            {1},
        )

        self.assertIsNotNone(result)
        self.assertEqual(
            result.mapping_id,
            "bundled",
        )
        self.assertEqual(
            result.confidence,
            "verified",
        )
        self.assertEqual(
            result.source,
            "bundled",
        )

    def test_verified_remote_can_replace_verified_bundled(
        self,
    ):
        device_catalog = self._client_with(
            "verified",
            "verified",
        )

        result = device_catalog.match(
            {
                "product_id": "abc123",
                "category": "cz",
            },
            {1},
        )

        self.assertIsNotNone(result)
        self.assertEqual(
            result.mapping_id,
            "remote",
        )
        self.assertEqual(
            result.confidence,
            "verified",
        )
        self.assertEqual(
            result.source,
            "remote",
        )
