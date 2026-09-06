"""Regression tests for residual Tuya Local light encodings."""

from __future__ import annotations

import unittest

from custom_components.localtuya.light import LocaltuyaLight


class ResidualLightRuntimeTests(unittest.TestCase):
    @staticmethod
    def _light(config=None):
        light = object.__new__(LocaltuyaLight)
        light._config = config or {}
        light._lower_brightness = 0
        light._upper_brightness = 255
        light._lower_color_brightness = int(light._config.get("color_brightness_lower", 0))
        light._upper_color_brightness = int(light._config.get("color_brightness_upper", 255))
        light._brightness_step = 1
        light._brightness_values = light._configured_brightness_values()
        light._color_temp_values = light._configured_color_temp_values()
        light._color_temp_step = int(light._config.get("color_temp_step", 1))
        light._light_power_mask = light._configured_light_power_mask()
        light._color_uses_rgb_encoding = bool(light._config.get("color_rgb_encoding", False))
        light._color_rgb_encoding_forced = light._color_uses_rgb_encoding
        return light

    def test_discrete_brightness_mapping_is_exact_on_read_and_nearest_on_write(self):
        light = self._light({"brightness_values": {"0": "level0", "85": "level1", "170": "level2", "255": "level3"}})
        self.assertEqual(light._raw_brightness_to_ha("level2"), 170)
        self.assertIsNone(light._raw_brightness_to_ha("LEVEL2"))
        self.assertEqual(light._ha_brightness_to_raw(200), "level2")
        self.assertEqual(light._ha_brightness_to_raw(250), "level3")

    def test_discrete_color_temperature_mapping(self):
        light = self._light({"color_temp_values": {"3000": 1, "4000": 2, "6000": 3}})
        light._min_kelvin = 3000
        light._max_kelvin = 6000
        self.assertEqual(light._raw_color_temp_to_kelvin(2), 4000)
        self.assertIsNone(light._raw_color_temp_to_kelvin(4))
        self.assertEqual(light._kelvin_to_raw_color_temp(4500), 2)
        self.assertEqual(light._kelvin_to_raw_color_temp(5500), 3)

    def test_extended_rgbhsv_scales_saturation_and_value(self):
        light = self._light({"color_rgb_encoding": True, "color_saturation_upper": 100, "color_brightness_lower": 0, "color_brightness_upper": 100})
        decoded = light._decode_color("ff000000646464")
        self.assertIsNotNone(decoded)
        hs, brightness = decoded
        self.assertEqual(hs, (100.0, 100.0))
        self.assertEqual(brightness, 255)
        encoded = light._encode_color((100, 100), 255)
        self.assertTrue(encoded.endswith("00646464"))

    def test_legacy_rgbhsv_can_use_saturation_100(self):
        light = self._light({"color_saturation_upper": 100, "color_brightness_lower": 0, "color_brightness_upper": 1000})
        decoded = light._decode_color("0064006403e8")
        self.assertEqual(decoded, ((100.0, 100.0), 255))
        self.assertEqual(light._encode_color((100, 100), 255), "0064006403e8")

    def test_masked_power_read_modify_write_preserves_other_bits(self):
        light = self._light({"light_power_mask": "0008"})
        light._state = "0011"
        self.assertFalse(light._power_state_from_raw("0011"))
        self.assertEqual(light._masked_power_write_value(True), "0019")
        light._state = "0019"
        self.assertTrue(light._power_state_from_raw("0019"))
        self.assertEqual(light._masked_power_write_value(False), "0011")


if __name__ == "__main__":
    unittest.main()
