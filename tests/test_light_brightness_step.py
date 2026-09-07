"""Regression tests for Tuya brightness step mappings."""

from __future__ import annotations

import unittest

from custom_components.localtuya.light import LocaltuyaLight


class LightBrightnessStepTests(unittest.TestCase):
    @staticmethod
    def _light(*, lower: int, upper: int, step: int | None = None) -> LocaltuyaLight:
        light = object.__new__(LocaltuyaLight)
        light._lower_brightness = lower
        light._upper_brightness = upper
        if step is not None:
            light._brightness_step = step
        return light

    def test_step_two_matches_tuya_local_write_quantization(self):
        light = self._light(lower=0, upper=100, step=2)
        self.assertEqual(light._ha_brightness_to_raw(127), 50)
        self.assertEqual(light._ha_brightness_to_raw(130), 52)
        self.assertEqual(light._ha_brightness_to_raw(255), 100)

    def test_step_ten_matches_tuya_local_write_quantization(self):
        light = self._light(lower=10, upper=1000, step=10)
        self.assertEqual(light._ha_brightness_to_raw(0), 10)
        self.assertEqual(light._ha_brightness_to_raw(128), 510)
        self.assertEqual(light._ha_brightness_to_raw(255), 1000)

    def test_missing_step_keeps_existing_mapping(self):
        light = self._light(lower=10, upper=1000)
        self.assertEqual(light._ha_brightness_to_raw(128), 507)


if __name__ == "__main__":
    unittest.main()
