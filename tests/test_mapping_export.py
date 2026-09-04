"""Tests for privacy-safe community mapping export."""

import json
import unittest

from custom_components.localtuya.mapping_export import (
    build_mapping_contribution_package,
    build_mapping_submission,
)


class TestMappingExport(
    unittest.TestCase
):
    """Community export tests."""

    def test_private_device_data_is_not_exported(
        self,
    ):
        device_data = {
            "device_id": "private-device-id",
            "host": "192.168.1.99",
            "local_key": "super-secret-key",
            "product_key": "product123",
            "protocol_version": "3.4",
            "dps_strings": [
                "1 (value: True)",
                "18 (value: 123)",
            ],
            "entities": [
                {
                    "id": 1,
                    "platform": "switch",
                    "friendly_name": "Kitchen Plug",
                    "restore_on_reconnect": False,
                    "is_passive_entity": False,
                    "current": 18,
                }
            ],
        }

        result = build_mapping_submission(
            device_data,
            cloud_device={
                "product_id": "product123",
                "category": "cz",
                "name": "My private kitchen device",
            },
        )

        serialized = json.dumps(
            result
        )

        self.assertNotIn(
            "super-secret-key",
            serialized,
        )
        self.assertNotIn(
            "192.168.1.99",
            serialized,
        )
        self.assertNotIn(
            "private-device-id",
            serialized,
        )
        self.assertNotIn(
            "Kitchen Plug",
            serialized,
        )
        self.assertNotIn(
            "My private kitchen device",
            serialized,
        )

        mapping = result[
            "mappings"
        ][0]

        self.assertEqual(
            mapping["match"][
                "product_id"
            ],
            "product123",
        )

    def test_all_referenced_dps_are_collected(
        self,
    ):
        device_data = {
            "product_key": "thermostat123",
            "protocol_version": "3.3",
            "dps_strings": [
                "1 (value: True)",
                "16 (value: 215)",
                "24 (value: 203)",
                "103 (value: heatcool_heat)",
            ],
            "entities": [
                {
                    "id": 1,
                    "platform": "climate",
                    "friendly_name": "Living Room",
                    "target_temperature_dp": 16,
                    "current_temperature_dp": 24,
                    "hvac_mode_dp": 103,
                    "max_temperature_const": 35,
                    "precision": 0.1,
                }
            ],
        }

        result = build_mapping_submission(
            device_data
        )

        required = result[
            "mappings"
        ][0]["match"][
            "required_dps"
        ]

        self.assertEqual(
            required,
            [1, 16, 24, 103],
        )

    def test_product_identifier_is_required(
        self,
    ):
        device_data = {
            "dps_strings": [
                "1 (value: True)",
            ],
            "entities": [
                {
                    "id": 1,
                    "platform": "switch",
                }
            ],
        }

        with self.assertRaises(
            ValueError
        ):
            build_mapping_submission(
                device_data
            )

    def test_missing_lan_dp_is_rejected(
        self,
    ):
        device_data = {
            "product_key": "product123",
            "dps_strings": [
                "1 (value: True)",
            ],
            "entities": [
                {
                    "id": 1,
                    "platform": "switch",
                    "current": 18,
                }
            ],
        }

        with self.assertRaises(
            ValueError
        ):
            build_mapping_submission(
                device_data
            )


class TestMappingContributionPackage(
    unittest.TestCase
):
    """Community contribution UX package tests."""

    @staticmethod
    def _device_data():
        return {
            "device_id": "private-device-id",
            "host": "192.168.50.44",
            "local_key": "private-local-key",
            "product_key": "product123",
            "protocol_version": "3.4",
            "dps_strings": [
                "1 (value: True)",
                "18 (value: 123)",
            ],
            "entities": [
                {
                    "id": 1,
                    "platform": "switch",
                    "friendly_name": "Private Kitchen Plug",
                    "current": 18,
                    "restore_on_reconnect": False,
                }
            ],
        }

    def test_package_contains_submission_preview_and_filename(
        self,
    ):
        package = build_mapping_contribution_package(
            self._device_data(),
            cloud_device={
                "product_id": "product123",
                "category": "cz",
                "name": "Private cloud name",
            },
        )

        submission = package["submission"]
        mapping = submission["mappings"][0]
        preview = package["preview"]

        self.assertEqual(
            preview["mapping_id"],
            mapping["id"],
        )

        self.assertEqual(
            preview["product_id"],
            "product123",
        )

        self.assertEqual(
            preview["category"],
            "cz",
        )

        self.assertEqual(
            preview["confidence"],
            "experimental",
        )

        self.assertEqual(
            preview["entity_count"],
            1,
        )

        self.assertEqual(
            preview["observed_dps"],
            [1, 18],
        )

        self.assertEqual(
            preview["required_dps"],
            [1, 18],
        )

        self.assertEqual(
            preview["protocol_version"],
            "3.4",
        )

        self.assertEqual(
            package["suggested_filename"],
            f'{mapping["id"]}.json',
        )


    def test_package_contains_catalog_navigation_only(
        self,
    ):
        package = build_mapping_contribution_package(
            self._device_data(),
        )

        self.assertEqual(
            package["repository_url"],
            (
                "https://github.com/"
                "MattiaFontana997/"
                "localtuya-device-catalog"
            ),
        )

        self.assertEqual(
            package["new_submission_url"],
            (
                "https://github.com/"
                "MattiaFontana997/"
                "localtuya-device-catalog/"
                "new/main/submissions"
            ),
        )

        self.assertFalse(
            package["privacy"][
                "automatic_upload"
            ]
        )


    def test_package_json_is_pretty_and_round_trips(
        self,
    ):
        package = build_mapping_contribution_package(
            self._device_data(),
        )

        parsed = json.loads(
            package["submission_json"]
        )

        self.assertEqual(
            parsed,
            package["submission"],
        )

        self.assertIn(
            "\n  \"schema_version\"",
            package["submission_json"],
        )


    def test_package_never_reintroduces_private_data(
        self,
    ):
        package = build_mapping_contribution_package(
            self._device_data(),
            cloud_device={
                "product_id": "product123",
                "category": "cz",
                "name": "Private cloud name",
                "id": "cloud-device-id",
                "uid": "cloud-user-id",
                "ip": "10.20.30.40",
                "local_key": "cloud-secret",
            },
        )

        serialized = json.dumps(
            package,
            ensure_ascii=False,
        )

        for private_value in (
            "private-device-id",
            "192.168.50.44",
            "private-local-key",
            "Private Kitchen Plug",
            "Private cloud name",
            "cloud-device-id",
            "cloud-user-id",
            "10.20.30.40",
            "cloud-secret",
        ):
            self.assertNotIn(
                private_value,
                serialized,
            )


class TestMappingExportOverrides(
    unittest.TestCase
):
    """Catalog overrides are explicit and minimal."""

    def test_generic_difference_becomes_override(
        self,
    ):
        device_data = {
            "product_key":
                "thermostat123",
            "protocol_version":
                "3.3",
            "dps_strings": [
                "1 (value: True)",
                "2 (value: manual)",
                "16 (value: 210)",
                "24 (value: 269)",
                "32 (value: 220)",
            ],
            "entities": [
                {
                    "id": 1,
                    "platform":
                        "climate",
                    "target_temperature_dp":
                        16,
                    "current_temperature_dp":
                        24,
                    "preset_dp":
                        2,
                    "preset_set":
                        (
                            "auto/manual/"
                            "temporary/boost/"
                            "holiday"
                        ),
                    "away_temperature_dp":
                        32,
                }
            ],
        }

        baseline_entities = [
            {
                "platform":
                    "climate",
                "config": {
                    "id": 1,
                    "platform":
                        "climate",
                    "target_temperature_dp":
                        16,
                    "current_temperature_dp":
                        24,
                    "preset_dp":
                        2,
                    "preset_set":
                        "auto/manual/holiday",
                },
            }
        ]

        result = (
            build_mapping_contribution_package(
                device_data,
                baseline_entities=(
                    baseline_entities
                ),
            )
        )

        entity = (
            result["submission"]
            ["mappings"][0]
            ["entities"][0]
        )

        self.assertEqual(
            entity["override_keys"],
            ["preset_set"],
        )

        # away_temperature_dp does not exist
        # in the generic baseline, so this is
        # enrichment rather than replacement.
        self.assertNotIn(
            "away_temperature_dp",
            entity["override_keys"],
        )



class TestMappingExportSensitiveKeyVariants(
    unittest.TestCase
):
    """Reject sensitive key spelling variants recursively."""

    def test_sensitive_key_variants_are_removed(
        self,
    ):
        device_data = {
            "product_key": "product123",
            "protocol_version": "3.4",
            "dps_strings": [
                "1 (value: True)",
            ],
            "entities": [
                {
                    "id": 1,
                    "platform": "switch",
                    "localKey":
                        "secret-one",
                    "device-id":
                        "secret-two",
                    "clientSecret":
                        "secret-three",
                    "nested": {
                        "User_ID":
                            "secret-four",
                        "friendlyName":
                            "Private Room",
                    },
                }
            ],
        }

        result = build_mapping_submission(
            device_data
        )

        serialized = json.dumps(
            result,
            ensure_ascii=False,
        )

        for secret in (
            "secret-one",
            "secret-two",
            "secret-three",
            "secret-four",
            "Private Room",
        ):
            self.assertNotIn(
                secret,
                serialized,
            )


if __name__ == "__main__":
    unittest.main()
