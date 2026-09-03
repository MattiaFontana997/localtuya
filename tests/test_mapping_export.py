"""Tests for privacy-safe community mapping export."""

import json
import unittest

from custom_components.localtuya.mapping_export import (
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


if __name__ == "__main__":
    unittest.main()
