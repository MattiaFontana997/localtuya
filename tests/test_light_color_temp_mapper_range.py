"""Regression tests for independent light color-temperature DP ranges."""

import unittest

from custom_components.localtuya.device_mapper import build_entity_candidates


class LightColorTempMapperRangeTests(unittest.TestCase):
    """Ensure CCT metadata is independent from brightness metadata."""

    def test_mapper_preserves_independent_color_temperature_range_and_step(self):
        device = {
            "name": "Independent CCT Light",
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
                    "dp_id": 22,
                    "code": "bright_value_v2",
                    "type": "Integer",
                    "values": '{"min":10,"max":1000,"scale":0,"step":1}',
                },
                {
                    "dp_id": 23,
                    "code": "temp_value_v2",
                    "type": "Integer",
                    "values": '{"min":100,"max":1100,"scale":0,"step":10}',
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
                    "code": "bright_value_v2",
                    "type": "Integer",
                    "values": '{"min":10,"max":1000,"scale":0,"step":1}',
                },
                {
                    "dp_id": 23,
                    "code": "temp_value_v2",
                    "type": "Integer",
                    "values": '{"min":100,"max":1100,"scale":0,"step":10}',
                },
            ],
        }

        candidates = build_entity_candidates(
            device,
            specification,
            available_dps={20, 22, 23},
        )
        lights = [candidate for candidate in candidates if candidate.platform == "light"]
        self.assertEqual(len(lights), 1)

        config = lights[0].config
        self.assertEqual(config["brightness"], 22)
        self.assertEqual(config["brightness_lower"], 10)
        self.assertEqual(config["brightness_upper"], 1000)
        self.assertEqual(config["color_temp"], 23)
        self.assertEqual(config["color_temp_lower"], 100)
        self.assertEqual(config["color_temp_upper"], 1100)
        self.assertEqual(config["color_temp_step"], 10)


if __name__ == "__main__":
    unittest.main()
