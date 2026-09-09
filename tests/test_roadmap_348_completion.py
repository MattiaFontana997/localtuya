"""Cross-cutting acceptance tests for completed roadmap items 3, 4, 6 and 8."""

from __future__ import annotations

import json
import unittest
from urllib.parse import parse_qs, urlparse

from custom_components.localtuya.device_catalog import (
    match_catalog_mapping,
    validate_catalog,
)
from custom_components.localtuya.mapping_export import build_mapping_contribution_package
from custom_components.localtuya.qr_onboarding import _parse_import_payload


def _mapping(
    mapping_id: str,
    *,
    confidence: str = "community",
    category: str | None = "cz",
    required_dps: list[int] | None = None,
    optional_dps: list[int] | None = None,
) -> dict:
    match = {
        "product_ids": ["product-1"],
        "required_dps": required_dps or [1],
        "optional_dps": optional_dps or [],
    }
    if category is not None:
        match["category"] = category
    return {
        "id": mapping_id,
        "confidence": confidence,
        "match": match,
        "entities": [
            {
                "platform": "switch",
                "config": {"id": 1, "platform": "switch"},
            }
        ],
    }


class CatalogAuthorityAcceptanceTests(unittest.TestCase):
    """Catalog selection must be deterministic and fail closed on ambiguity."""

    def test_verified_beats_community_independent_of_order(self):
        catalog = validate_catalog(
            {
                "schema_version": 2,
                "mappings": [
                    _mapping("community", confidence="community"),
                    _mapping("verified", confidence="verified", category=None),
                ],
            }
        )
        result = match_catalog_mapping(
            catalog,
            {"product_id": "product-1", "category": "cz"},
            {1},
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.mapping_id, "verified")

    def test_more_specific_required_dps_wins_at_equal_trust(self):
        catalog = validate_catalog(
            {
                "schema_version": 2,
                "mappings": [
                    _mapping("generic", confidence="verified", required_dps=[1]),
                    _mapping("specific", confidence="verified", required_dps=[1, 2]),
                ],
            }
        )
        result = match_catalog_mapping(
            catalog,
            {"product_id": "product-1", "category": "cz"},
            {1, 2},
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.mapping_id, "specific")

    def test_equally_authoritative_matches_are_rejected(self):
        catalog = validate_catalog(
            {
                "schema_version": 2,
                "mappings": [
                    _mapping("first", confidence="verified"),
                    _mapping("second", confidence="verified"),
                ],
            }
        )
        self.assertIsNone(
            match_catalog_mapping(
                catalog,
                {"product_id": "product-1", "category": "cz"},
                {1},
            )
        )


class GatewayMetadataAcceptanceTests(unittest.TestCase):
    """Gateway-backed children keep routing identity without false positives."""

    def test_true_subdevice_uuid_becomes_cid(self):
        device = _parse_import_payload(
            json.dumps(
                {
                    "id": "child-1",
                    "key": "gateway-key",
                    "gateway_id": "gateway-1",
                    "sub": "true",
                    "uuid": "node-from-uuid",
                }
            )
        )["child-1"]
        self.assertEqual(device["gateway_id"], "gateway-1")
        self.assertEqual(device["node_id"], "node-from-uuid")

    def test_string_false_never_promotes_uuid_to_cid(self):
        device = _parse_import_payload(
            json.dumps(
                {
                    "id": "direct-1",
                    "key": "device-key",
                    "gateway_id": "gateway-1",
                    "sub": "false",
                    "uuid": "not-a-cid",
                }
            )
        )["direct-1"]
        self.assertNotIn("node_id", device)


class ContributionAcceptanceTests(unittest.TestCase):
    """Community submission is prefilled when safe and usable when oversized."""

    @staticmethod
    def _device_data(extra_value: str = "") -> dict:
        entity = {
            "id": 1,
            "platform": "switch",
            "current": 18,
        }
        if extra_value:
            entity["large_safe_value"] = extra_value
        return {
            "device_id": "private-device",
            "host": "192.168.1.50",
            "local_key": "private-key",
            "product_key": "product-1",
            "protocol_version": "3.4",
            "dps_strings": ["1 (value: True)", "18 (value: 1)"],
            "entities": [entity],
        }

    def test_normal_submission_has_complete_github_prefill(self):
        package = build_mapping_contribution_package(self._device_data())
        query = parse_qs(urlparse(package["new_submission_url"]).query)
        self.assertTrue(package["prefill_complete"])
        self.assertEqual(query["filename"], [package["suggested_filename"]])
        self.assertEqual(json.loads(query["value"][0]), package["submission"])

    def test_oversized_submission_fails_over_without_truncating_json(self):
        package = build_mapping_contribution_package(
            self._device_data("x" * 10000)
        )
        query = parse_qs(urlparse(package["new_submission_url"]).query)
        self.assertFalse(package["prefill_complete"])
        self.assertNotIn("value", query)
        self.assertEqual(json.loads(package["submission_json"]), package["submission"])


if __name__ == "__main__":
    unittest.main()
