"""Tests for safe productless catalog fingerprints."""

import unittest

from custom_components.localtuya.device_catalog import (
    match_catalog_mapping,
    validate_catalog,
)


def fingerprint(mapping_id, required, optional=None, *, confidence="experimental"):
    return {
        "id": mapping_id,
        "confidence": confidence,
        "match": {
            "product_ids": [],
            "category": None,
            "required_dps": required,
            "optional_dps": optional or [],
            "fingerprint": {"mode": "exact_dps"},
        },
        "entities": [
            {
                "platform": "switch",
                "config": {"id": required[0], "platform": "switch"},
            }
        ],
        "provenance": {
            "source": "make-all/tuya-local",
            "path": "custom_components/tuya_local/devices/example.yaml",
            "license": "MIT",
        },
    }


class TestSafeFingerprintCatalog(unittest.TestCase):
    def test_unique_exact_fingerprint_matches_without_product_id(self):
        catalog = validate_catalog({
            "schema_version": 3,
            "mappings": [fingerprint("profile-a", [1, 2], [3])],
        })
        result = match_catalog_mapping(catalog, {}, {1, 2, 3})
        self.assertIsNotNone(result)
        self.assertEqual(result.mapping_id, "profile-a")
        self.assertEqual(result.match_kind, "fingerprint")
        self.assertEqual(result.product_id, "")

    def test_unknown_observed_dp_rejects_fingerprint(self):
        catalog = validate_catalog({
            "schema_version": 3,
            "mappings": [fingerprint("profile-a", [1, 2], [3])],
        })
        self.assertIsNone(match_catalog_mapping(catalog, {}, {1, 2, 3, 99}))

    def test_missing_required_dp_rejects_fingerprint(self):
        catalog = validate_catalog({
            "schema_version": 3,
            "mappings": [fingerprint("profile-a", [1, 2], [3])],
        })
        self.assertIsNone(match_catalog_mapping(catalog, {}, {1, 3}))

    def test_product_id_never_falls_back_to_productless_fingerprint(self):
        catalog = validate_catalog({
            "schema_version": 3,
            "mappings": [fingerprint("profile-a", [1, 2])],
        })
        self.assertIsNone(match_catalog_mapping(
            catalog, {"product_id": "real-product"}, {1, 2}
        ))

    def test_equal_best_fingerprints_fail_closed(self):
        catalog = validate_catalog({
            "schema_version": 3,
            "mappings": [
                fingerprint("profile-a", [1, 2]),
                fingerprint("profile-b", [1, 2]),
            ],
        })
        self.assertIsNone(match_catalog_mapping(catalog, {}, {1, 2}))

    def test_more_specific_unique_fingerprint_wins(self):
        catalog = validate_catalog({
            "schema_version": 3,
            "mappings": [
                fingerprint("profile-a", [1], [2]),
                fingerprint("profile-b", [1, 2]),
            ],
        })
        result = match_catalog_mapping(catalog, {}, {1, 2})
        self.assertIsNotNone(result)
        self.assertEqual(result.mapping_id, "profile-b")

    def test_verified_productless_fingerprint_is_rejected(self):
        catalog = validate_catalog({
            "schema_version": 3,
            "mappings": [fingerprint("profile-a", [1], confidence="verified")],
        })
        self.assertEqual(catalog["mappings"], [])

    def test_v2_product_mapping_remains_compatible(self):
        catalog = validate_catalog({
            "schema_version": 2,
            "mappings": [{
                "id": "product-a",
                "confidence": "verified",
                "match": {
                    "product_ids": ["abc"],
                    "category": "kg",
                    "required_dps": [1],
                    "optional_dps": [],
                },
                "entities": [{
                    "platform": "switch",
                    "config": {"id": 1, "platform": "switch"},
                }],
            }],
        })
        result = match_catalog_mapping(
            catalog, {"product_id": "abc", "category": "kg"}, {1}
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.match_kind, "product")


if __name__ == "__main__":
    unittest.main()
