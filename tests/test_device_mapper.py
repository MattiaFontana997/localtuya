"""Tests for the generic Tuya metadata mapper."""

import unittest

from custom_components.localtuya.device_mapper import (
    MappingConfidence,
    build_entity_candidates,
)


class DeviceMapperTests(unittest.TestCase):
    """Test generic entity mapping."""

    @staticmethod
    def candidate(candidates, platform, dp_id):
        matches = [
            candidate
            for candidate in candidates
            if (
                candidate.platform == platform
                and candidate.primary_dp == dp_id
            )
        ]

        if len(matches) != 1:
            raise AssertionError(
                f"Expected one {platform} DP{dp_id}, "
                f"found {len(matches)}"
            )

        return matches[0]

    def test_number_select_switch_mapping(self):
        """Writable numeric/enum DPS become MEDIUM suggestions."""
        device = {
            "name": "Generic Device",
            "category": "test",
        }

        specification = {
            "functions": [
                {
                    "dp_id": 1,
                    "code": "switch_1",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 10,
                    "code": "temperature_offset",
                    "type": "Integer",
                    "values": (
                        '{"unit":"℃","min":-30,'
                        '"max":30,"scale":1,"step":5}'
                    ),
                },
                {
                    "dp_id": 11,
                    "code": "relay_status",
                    "type": "Enum",
                    "values": (
                        '{"range":["off","on","memory"]}'
                    ),
                },
            ],
            "status": [
                {
                    "dp_id": 1,
                    "code": "switch_1",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 10,
                    "code": "temperature_offset",
                    "type": "Integer",
                    "values": (
                        '{"unit":"℃","min":-30,'
                        '"max":30,"scale":1,"step":5}'
                    ),
                },
                {
                    "dp_id": 11,
                    "code": "relay_status",
                    "type": "Enum",
                    "values": (
                        '{"range":["off","on","memory"]}'
                    ),
                },
            ],
        }

        candidates = build_entity_candidates(
            device,
            specification,
            available_dps={1, 10, 11},
        )

        switch = self.candidate(
            candidates,
            "switch",
            1,
        )
        number = self.candidate(
            candidates,
            "number",
            10,
        )
        select = self.candidate(
            candidates,
            "select",
            11,
        )

        self.assertEqual(
            switch.confidence,
            MappingConfidence.HIGH,
        )

        self.assertEqual(
            number.confidence,
            MappingConfidence.MEDIUM,
        )
        self.assertEqual(
            number.config["min_value"],
            -3.0,
        )
        self.assertEqual(
            number.config["max_value"],
            3.0,
        )
        self.assertEqual(
            number.config["step_size"],
            0.5,
        )
        self.assertEqual(
            number.config["scaling"],
            0.1,
        )

        self.assertEqual(
            select.confidence,
            MappingConfidence.MEDIUM,
        )
        self.assertEqual(
            select.config["select_options"],
            "off;on;memory",
        )

    def test_binary_sensor_mapping(self):
        """Only semantic read-only booleans become binary sensors."""
        device = {
            "name": "Test Sensor",
            "category": "test",
        }

        specification = {
            "functions": [
                {
                    "dp_id": 1,
                    "code": "switch_1",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 3,
                    "code": "child_lock",
                    "type": "Boolean",
                    "values": "{}",
                },
            ],
            "status": [
                {
                    "dp_id": 1,
                    "code": "switch_1",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 2,
                    "code": "doorcontact_state",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 3,
                    "code": "child_lock",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 4,
                    "code": "switch_status",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 5,
                    "code": "battery_low",
                    "type": "Boolean",
                    "values": "{}",
                },
            ],
        }

        candidates = build_entity_candidates(
            device,
            specification,
            available_dps={1, 2, 3, 4, 5},
        )

        switch = self.candidate(
            candidates,
            "switch",
            1,
        )
        door = self.candidate(
            candidates,
            "binary_sensor",
            2,
        )
        battery = self.candidate(
            candidates,
            "binary_sensor",
            5,
        )

        self.assertEqual(
            switch.confidence,
            MappingConfidence.HIGH,
        )

        self.assertEqual(
            door.config["device_class"],
            "door",
        )
        self.assertEqual(
            door.config["state_on"],
            "True",
        )
        self.assertEqual(
            door.config["state_off"],
            "False",
        )

        self.assertEqual(
            battery.config["device_class"],
            "battery",
        )

        # Writable child_lock is not a sensor.
        self.assertFalse(
            any(
                candidate.primary_dp == 3
                for candidate in candidates
            )
        )

        # Read-only switch_status must not become a switch.
        self.assertFalse(
            any(
                candidate.primary_dp == 4
                for candidate in candidates
            )
        )

    def test_generic_thermostat_remains_product_agnostic(self):
        """Generic mapper contains no product-specific HVAC knowledge."""
        device = {
            "name": "Termostato",
            "category": "wk",
            "product_id": "wxmbjwpt8yea7bag",
        }

        specification = {
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

        candidates = build_entity_candidates(
            device,
            specification,
            available_dps={
                1,
                2,
                16,
                24,
                103,
            },
        )

        climate = self.candidate(
            candidates,
            "climate",
            1,
        )

        self.assertEqual(
            climate.confidence,
            MappingConfidence.HIGH,
        )
        self.assertEqual(
            climate.config["target_temperature_dp"],
            16,
        )
        self.assertEqual(
            climate.config["current_temperature_dp"],
            24,
        )
        self.assertEqual(
            climate.config["precision"],
            0.1,
        )
        self.assertEqual(
            climate.config["target_precision"],
            0.1,
        )
        self.assertEqual(
            climate.config["temperature_step"],
            0.5,
        )
        self.assertNotIn(
            "hvac_mode_dp",
            climate.config,
        )

        self.assertNotIn(
            "hvac_mode_set",
            climate.config,
        )

        self.assertNotIn(
            103,
            climate.referenced_dps,
        )

    def test_generic_mapper_does_not_infer_hvac_from_dp103(self):
        """DP103 alone must not activate another product's override."""
        device = {
            "name": "Other Thermostat",
            "category": "wk",
            "product_id": "another-product",
        }

        specification = {
            "functions": [
                {
                    "dp_id": 1,
                    "code": "switch",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 16,
                    "code": "temp_set",
                    "type": "Integer",
                    "values": (
                        '{"unit":"℃","min":50,'
                        '"max":350,"scale":1,"step":5}'
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
                    "dp_id": 16,
                    "code": "temp_set",
                    "type": "Integer",
                    "values": (
                        '{"unit":"℃","min":50,'
                        '"max":350,"scale":1,"step":5}'
                    ),
                },
                {
                    "dp_id": 24,
                    "code": "temp_current",
                    "type": "Integer",
                    "values": (
                        '{"unit":"℃","min":0,'
                        '"max":400,"scale":1,"step":1}'
                    ),
                },
            ],
        }

        candidates = build_entity_candidates(
            device,
            specification,
            available_dps={
                1,
                16,
                24,
                103,
            },
        )

        climate = self.candidate(
            candidates,
            "climate",
            1,
        )

        self.assertNotIn(
            "hvac_mode_dp",
            climate.config,
        )

    def test_tecnolite_light_mapping(self):
        """Known CCT metadata produces one complete generic light."""
        device = {
            "name": "Bathroom Light",
            "category": "dj",
        }

        specification = {
            "functions": [
                {
                    "dp_id": 20,
                    "code": "switch_led",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 21,
                    "code": "work_mode",
                    "type": "Enum",
                    "values": (
                        '{"range":'
                        '["white","colour","scene","music"]}'
                    ),
                },
                {
                    "dp_id": 22,
                    "code": "bright_value_v2",
                    "type": "Integer",
                    "values": (
                        '{"min":10,"max":1000,'
                        '"scale":0,"step":1}'
                    ),
                },
                {
                    "dp_id": 23,
                    "code": "temp_value_v2",
                    "type": "Integer",
                    "values": (
                        '{"min":0,"max":1000,'
                        '"scale":0,"step":1}'
                    ),
                },
            ],
            "status": [
                {
                    "dp_id": 20,
                    "code": "switch_led",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 21,
                    "code": "work_mode",
                    "type": "Enum",
                    "values": (
                        '{"range":'
                        '["white","colour","scene","music"]}'
                    ),
                },
                {
                    "dp_id": 22,
                    "code": "bright_value_v2",
                    "type": "Integer",
                    "values": (
                        '{"min":10,"max":1000,'
                        '"scale":0,"step":1}'
                    ),
                },
                {
                    "dp_id": 23,
                    "code": "temp_value_v2",
                    "type": "Integer",
                    "values": (
                        '{"min":0,"max":1000,'
                        '"scale":0,"step":1}'
                    ),
                },
            ],
        }

        candidates = build_entity_candidates(
            device,
            specification,
            available_dps={20, 21, 22, 23},
        )

        light = self.candidate(
            candidates,
            "light",
            20,
        )

        self.assertEqual(
            light.confidence,
            MappingConfidence.HIGH,
        )
        self.assertEqual(
            light.config["brightness"],
            22,
        )
        self.assertEqual(
            light.config["color_temp"],
            23,
        )
        self.assertEqual(
            light.config["color_mode"],
            21,
        )
        self.assertEqual(
            light.config["brightness_lower"],
            10,
        )
        self.assertEqual(
            light.config["brightness_upper"],
            1000,
        )

    def test_standard_cover_mapping(self):
        """Standard curtain DPS become one positional cover."""
        device = {
            "name": "Living Curtain",
            "category": "cl",
        }

        specification = {
            "functions": [
                {
                    "dp_id": 1,
                    "code": "control",
                    "type": "Enum",
                    "values": (
                        '{"range":'
                        '["open","stop","close","continue"]}'
                    ),
                },
                {
                    "dp_id": 2,
                    "code": "percent_control",
                    "type": "Integer",
                    "values": (
                        '{"unit":"%","min":0,'
                        '"max":100,"scale":0,"step":1}'
                    ),
                },
            ],
            "status": [
                {
                    "dp_id": 1,
                    "code": "control",
                    "type": "Enum",
                    "values": (
                        '{"range":'
                        '["open","stop","close","continue"]}'
                    ),
                },
                {
                    "dp_id": 2,
                    "code": "percent_control",
                    "type": "Integer",
                    "values": (
                        '{"unit":"%","min":0,'
                        '"max":100,"scale":0,"step":1}'
                    ),
                },
                {
                    "dp_id": 3,
                    "code": "percent_state",
                    "type": "Integer",
                    "values": (
                        '{"unit":"%","min":0,'
                        '"max":100,"scale":0,"step":1}'
                    ),
                },
            ],
        }

        candidates = build_entity_candidates(
            device,
            specification,
            available_dps={1, 2, 3},
        )

        cover = self.candidate(
            candidates,
            "cover",
            1,
        )

        self.assertEqual(
            cover.confidence,
            MappingConfidence.HIGH,
        )
        self.assertEqual(
            cover.config["commands_set"],
            "open_close_stop",
        )
        self.assertEqual(
            cover.config["positioning_mode"],
            "position",
        )
        self.assertEqual(
            cover.config["set_position_dp"],
            2,
        )
        self.assertEqual(
            cover.config["current_position_dp"],
            3,
        )
        self.assertEqual(
            cover.referenced_dps,
            (1, 2, 3),
        )

        # Position DPs are consumed by the cover and must not
        # leak into generic number entities.
        self.assertFalse(
            any(
                candidate.platform == "number"
                and candidate.primary_dp in {2, 3}
                for candidate in candidates
            )
        )

    def test_standard_fan_mapping(self):
        """Standard fan DPS become one composite fan."""
        device = {
            "name": "Bedroom Fan",
            "category": "fs",
        }

        specification = {
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
                        '["nature","sleep","fresh","smart"]}'
                    ),
                },
                {
                    "dp_id": 3,
                    "code": "fan_speed_percent",
                    "type": "Integer",
                    "values": (
                        '{"min":1,"max":100,'
                        '"scale":0,"step":1}'
                    ),
                },
                {
                    "dp_id": 4,
                    "code": "switch_horizontal",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 5,
                    "code": "switch_vertical",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 6,
                    "code": "fan_direction",
                    "type": "Enum",
                    "values": (
                        '{"range":'
                        '["forward","reverse"]}'
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
                        '["nature","sleep","fresh","smart"]}'
                    ),
                },
                {
                    "dp_id": 3,
                    "code": "fan_speed_percent",
                    "type": "Integer",
                    "values": (
                        '{"min":1,"max":100,'
                        '"scale":0,"step":1}'
                    ),
                },
                {
                    "dp_id": 4,
                    "code": "switch_horizontal",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 5,
                    "code": "switch_vertical",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 6,
                    "code": "fan_direction",
                    "type": "Enum",
                    "values": (
                        '{"range":'
                        '["forward","reverse"]}'
                    ),
                },
            ],
        }

        candidates = build_entity_candidates(
            device,
            specification,
            available_dps={
                1,
                2,
                3,
                4,
                5,
                6,
            },
        )

        fan = self.candidate(
            candidates,
            "fan",
            1,
        )

        self.assertEqual(
            fan.confidence,
            MappingConfidence.HIGH,
        )
        self.assertEqual(
            fan.config["fan_speed_control"],
            3,
        )
        self.assertEqual(
            fan.config["fan_speed_min"],
            1,
        )
        self.assertEqual(
            fan.config["fan_speed_max"],
            100,
        )
        self.assertEqual(
            fan.config["fan_dps_type"],
            "int",
        )
        self.assertEqual(
            fan.config["fan_oscillating_control"],
            4,
        )
        self.assertEqual(
            fan.config["fan_direction"],
            6,
        )
        self.assertEqual(
            fan.config["fan_direction_forward"],
            "forward",
        )
        self.assertEqual(
            fan.config["fan_direction_reverse"],
            "reverse",
        )

        # The unconsumed fan mode remains an optional select.
        mode = self.candidate(
            candidates,
            "select",
            2,
        )

        self.assertEqual(
            mode.confidence,
            MappingConfidence.MEDIUM,
        )

        # Fan power and swing controls must not leak out as
        # generic switches.
        self.assertFalse(
            any(
                candidate.platform == "switch"
                and candidate.primary_dp in {
                    1,
                    4,
                    5,
                }
                for candidate in candidates
            )
        )

        # Speed and direction belong to the fan.
        self.assertFalse(
            any(
                candidate.primary_dp in {
                    3,
                    6,
                }
                and candidate.platform
                in {"number", "select"}
                for candidate in candidates
            )
        )

    def test_ceiling_fan_light_mapping(self):
        """Ceiling fan light exposes separate light and fan entities."""
        device = {
            "name": "Ceiling Unit",
            "category": "fsd",
        }

        specification = {
            "functions": [
                {
                    "dp_id": 20,
                    "code": "switch_led",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 22,
                    "code": "bright_value",
                    "type": "Integer",
                    "values": (
                        '{"min":10,"max":1000,'
                        '"scale":0,"step":1}'
                    ),
                },
                {
                    "dp_id": 23,
                    "code": "temp_value",
                    "type": "Integer",
                    "values": (
                        '{"min":0,"max":1000,'
                        '"scale":0,"step":1}'
                    ),
                },
                {
                    "dp_id": 60,
                    "code": "fan_switch",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 61,
                    "code": "fan_speed",
                    "type": "Integer",
                    "values": (
                        '{"unit":"%","min":1,'
                        '"max":100,"scale":0,"step":1}'
                    ),
                },
                {
                    "dp_id": 63,
                    "code": "fan_direction",
                    "type": "Enum",
                    "values": (
                        '{"range":'
                        '["forward","reverse"]}'
                    ),
                },
            ],
            "status": [
                {
                    "dp_id": 20,
                    "code": "switch_led",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 22,
                    "code": "bright_value",
                    "type": "Integer",
                    "values": (
                        '{"min":10,"max":1000,'
                        '"scale":0,"step":1}'
                    ),
                },
                {
                    "dp_id": 23,
                    "code": "temp_value",
                    "type": "Integer",
                    "values": (
                        '{"min":0,"max":1000,'
                        '"scale":0,"step":1}'
                    ),
                },
                {
                    "dp_id": 60,
                    "code": "fan_switch",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 61,
                    "code": "fan_speed",
                    "type": "Integer",
                    "values": (
                        '{"unit":"%","min":1,'
                        '"max":100,"scale":0,"step":1}'
                    ),
                },
                {
                    "dp_id": 63,
                    "code": "fan_direction",
                    "type": "Enum",
                    "values": (
                        '{"range":'
                        '["forward","reverse"]}'
                    ),
                },
            ],
        }

        candidates = build_entity_candidates(
            device,
            specification,
            available_dps={
                20,
                22,
                23,
                60,
                61,
                63,
            },
        )

        light = self.candidate(
            candidates,
            "light",
            20,
        )

        fan = self.candidate(
            candidates,
            "fan",
            60,
        )

        self.assertEqual(
            light.confidence,
            MappingConfidence.HIGH,
        )
        self.assertEqual(
            fan.confidence,
            MappingConfidence.HIGH,
        )

        self.assertEqual(
            fan.config["fan_speed_control"],
            61,
        )
        self.assertEqual(
            fan.config["fan_direction"],
            63,
        )



if __name__ == "__main__":
    unittest.main()
