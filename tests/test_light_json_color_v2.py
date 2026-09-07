"""Regression tests for Tuya JSON colour_data_v2 payloads."""

import json
import unittest

from custom_components.localtuya.const import (
    CONF_COLOR_BRIGHTNESS_LOWER,
    CONF_COLOR_BRIGHTNESS_UPPER,
    CONF_COLOR_JSON_ENCODING,
    CONF_COLOR_SATURATION_UPPER,
)
from custom_components.localtuya.device_mapper import build_entity_candidates
from custom_components.localtuya.light import LocaltuyaLight


class LightJsonColorV2Tests(unittest.TestCase):
    """Cover deterministic Tuya v2 JSON HSV semantics."""

    @staticmethod
    def _light(*, forced_json=True):
        light = object.__new__(LocaltuyaLight)
        light._config = {
            CONF_COLOR_JSON_ENCODING: forced_json,
            CONF_COLOR_SATURATION_UPPER: 1000,
            CONF_COLOR_BRIGHTNESS_LOWER: 0,
            CONF_COLOR_BRIGHTNESS_UPPER: 1000,
        }
        light._lower_color_brightness = 0
        light._upper_color_brightness = 1000
        light._color_json_encoding = forced_json
        light._color_json_payload_as_string = False
        light._color_rgb_encoding_forced = False
        light._color_uses_rgb_encoding = False
        return light

    def test_decode_json_object_scales_v2_hsv(self):
        light = self._light()
        hs, brightness = light._decode_color({"h": 201, "s": 511, "v": 899})

        self.assertEqual(hs[0], 201.0)
        self.assertAlmostEqual(hs[1], 51.1, places=3)
        self.assertEqual(brightness, 229)

    def test_encode_json_object_scales_v2_hsv(self):
        light = self._light()
        payload = light._encode_color((201, 51.1), 255)

        self.assertEqual(payload, {"h": 201, "s": 511, "v": 1000})

    def test_json_string_read_preserves_string_write_transport(self):
        light = self._light(forced_json=False)
        hs, brightness = light._decode_color('{"h":120,"s":500,"v":1000}')

        self.assertEqual(hs, (120.0, 50.0))
        self.assertEqual(brightness, 255)
        encoded = light._encode_color(hs, brightness)
        self.assertIsInstance(encoded, str)
        self.assertEqual(json.loads(encoded), {"h": 120, "s": 500, "v": 1000})

    def test_mapper_enables_only_v2_json_color(self):
        device = {"name": "JSON RGB Light", "category": "dj"}
        specification = {
            "functions": [
                {"dp_id": 20, "code": "switch_led", "type": "Boolean", "values": "{}"},
                {
                    "dp_id": 21,
                    "code": "work_mode",
                    "type": "Enum",
                    "values": '{"range":["white","colour","scene","music"]}',
                },
                {"dp_id": 24, "code": "colour_data_v2", "type": "Json", "values": "{}"},
            ],
            "status": [
                {"dp_id": 20, "code": "switch_led", "type": "Boolean", "values": "{}"},
                {
                    "dp_id": 21,
                    "code": "work_mode",
                    "type": "Enum",
                    "values": '{"range":["white","colour","scene","music"]}',
                },
                {"dp_id": 24, "code": "colour_data_v2", "type": "Json", "values": "{}"},
            ],
        }

        candidates = build_entity_candidates(
            device,
            specification,
            available_dps={20, 21, 24},
        )
        light = next(candidate for candidate in candidates if candidate.platform == "light")

        self.assertEqual(light.config["color"], 24)
        self.assertTrue(light.config["color_json_encoding"])
        self.assertEqual(light.config["color_saturation_upper"], 1000)
        self.assertEqual(light.config["color_brightness_lower"], 0)
        self.assertEqual(light.config["color_brightness_upper"], 1000)
        self.assertIn("colour_data_v2", light.matched_codes)

    def test_mapper_keeps_legacy_json_color_fail_closed(self):
        device = {"name": "Ambiguous JSON RGB Light", "category": "dj"}
        specification = {
            "functions": [
                {"dp_id": 20, "code": "switch_led", "type": "Boolean", "values": "{}"},
                {"dp_id": 24, "code": "colour_data", "type": "Json", "values": "{}"},
            ],
            "status": [
                {"dp_id": 20, "code": "switch_led", "type": "Boolean", "values": "{}"},
                {"dp_id": 24, "code": "colour_data", "type": "Json", "values": "{}"},
            ],
        }

        candidates = build_entity_candidates(
            device,
            specification,
            available_dps={20, 24},
        )
        light = next(candidate for candidate in candidates if candidate.platform == "light")

        self.assertNotIn("color", light.config)
        self.assertNotIn("color_json_encoding", light.config)
        self.assertNotIn("colour_data", light.matched_codes)


if __name__ == "__main__":
    unittest.main()
