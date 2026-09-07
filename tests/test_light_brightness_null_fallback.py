"""Regression tests for Tuya null brightness read fallbacks."""

from __future__ import annotations

import unittest

from custom_components.localtuya.light import LocaltuyaLight


class LightBrightnessNullFallbackTests(unittest.TestCase):
    @staticmethod
    def _light(config=None) -> LocaltuyaLight:
        light = object.__new__(LocaltuyaLight)
        light._lower_brightness = 0
        light._upper_brightness = 1000
        if config is not None:
            light._config = config
        return light

    def test_null_without_fallback_remains_unknown(self):
        self.assertIsNone(self._light({})._raw_brightness_to_ha(None))

    def test_null_fallback_is_applied_on_read_only(self):
        light = self._light({"brightness_null_value": 0})
        self.assertEqual(light._raw_brightness_to_ha(None), 0)
        self.assertEqual(light._raw_brightness_to_ha(500), 128)

    def test_legacy_synthetic_light_without_config_remains_safe(self):
        self.assertIsNone(self._light()._raw_brightness_to_ha(None))


if __name__ == "__main__":
    unittest.main()
