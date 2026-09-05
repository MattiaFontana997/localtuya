"""Regression tests for independent Tuya HSV brightness ranges."""

from __future__ import annotations

import unittest

from custom_components.localtuya.light import LocaltuyaLight


class LightColorBrightnessRangeTests(unittest.TestCase):
    @staticmethod
    def _light(
        *,
        white_lower: int = 10,
        white_upper: int = 1000,
        color_lower: int = 0,
        color_upper: int = 1000,
    ) -> LocaltuyaLight:
        light = object.__new__(LocaltuyaLight)
        light._lower_brightness = white_lower
        light._upper_brightness = white_upper
        light._lower_color_brightness = color_lower
        light._upper_color_brightness = color_upper
        light._color_uses_rgb_encoding = False
        return light

    def test_white_and_hsv_ranges_are_independent(self):
        light = self._light()

        self.assertEqual(light._ha_brightness_to_raw(0), 10)
        self.assertEqual(light._ha_brightness_to_raw(255), 1000)
        self.assertEqual(light._ha_brightness_to_raw_color(0), 0)
        self.assertEqual(light._ha_brightness_to_raw_color(255), 1000)

    def test_standard_hsv_decode_uses_color_range(self):
        light = self._light()

        hs, brightness = light._decode_color("007803e80000")

        self.assertEqual(hs, (120.0, 100.0))
        self.assertEqual(brightness, 0)
        self.assertFalse(light._color_uses_rgb_encoding)

        hs, brightness = light._decode_color("007803e803e8")

        self.assertEqual(hs, (120.0, 100.0))
        self.assertEqual(brightness, 255)

    def test_standard_hsv_encode_uses_color_range(self):
        light = self._light()

        self.assertEqual(
            light._encode_color((120.0, 100.0), 0),
            "007803e80000",
        )
        self.assertEqual(
            light._encode_color((120.0, 100.0), 255),
            "007803e803e8",
        )

    def test_legacy_shared_range_remains_equivalent(self):
        light = self._light(
            white_lower=29,
            white_upper=1000,
            color_lower=29,
            color_upper=1000,
        )

        for brightness in (0, 64, 128, 255):
            self.assertEqual(
                light._ha_brightness_to_raw_color(brightness),
                light._ha_brightness_to_raw(brightness),
            )

        for raw_value in (29, 250, 500, 1000):
            self.assertEqual(
                light._raw_color_brightness_to_ha(raw_value),
                light._raw_brightness_to_ha(raw_value),
            )

    def test_extended_rgb_hsv_payload_keeps_native_8_bit_value(self):
        light = self._light(color_lower=100, color_upper=1000)

        # RRGGBB + HHHH + SS + VV. The long Tuya encoding uses an 8-bit
        # brightness component and must not use the configurable HSV V range.
        hs, brightness = light._decode_color("ff00000078ff80")

        self.assertEqual(hs, (120.0, 100.0))
        self.assertEqual(brightness, 128)
        self.assertTrue(light._color_uses_rgb_encoding)


if __name__ == "__main__":
    unittest.main()
