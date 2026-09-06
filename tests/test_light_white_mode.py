"""Regression tests for catalog-provided dedicated RGBW white mode."""

from __future__ import annotations

import unittest

from homeassistant.components.light import ATTR_WHITE, ColorMode, LightEntityFeature
from homeassistant.const import CONF_BRIGHTNESS

from custom_components.localtuya.const import (
    CONF_COLOR,
    CONF_COLOR_MODE,
    CONF_WHITE_MODE,
)
from custom_components.localtuya.light import LocaltuyaLight, Mode


class _FakeDevice:
    def __init__(self):
        self.states = None

    async def set_dps(self, states):
        self.states = states


class LightWhiteModeTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _light() -> LocaltuyaLight:
        light = object.__new__(LocaltuyaLight)
        light._config = {
            CONF_BRIGHTNESS: 3,
            CONF_COLOR: 5,
            CONF_COLOR_MODE: 2,
            CONF_WHITE_MODE: True,
        }
        light._white_mode_enabled = True
        light._modes = Mode()
        light._attr_color_mode = None
        light._attr_brightness = 128
        light._attr_hs_color = (120.0, 100.0)
        light._attr_is_on = True
        light._attr_supported_features = LightEntityFeature(0)
        light._effects = {}
        light._scenes = {}
        light._music_mode_enabled = False
        light._lower_brightness = 25
        light._upper_brightness = 255
        light._lower_color_brightness = 0
        light._upper_color_brightness = 255
        light._color_rgb_encoding_forced = True
        light._color_uses_rgb_encoding = True
        light._dp_id = 1
        light._device = _FakeDevice()
        return light

    def test_white_mode_is_exposed_alongside_hs(self):
        light = self._light()

        modes = light._build_supported_color_modes()

        self.assertEqual(modes, {ColorMode.HS, ColorMode.WHITE})
        light._attr_supported_color_modes = modes
        self.assertEqual(light._determine_color_mode("white"), ColorMode.WHITE)
        self.assertEqual(light._determine_color_mode("colour"), ColorMode.HS)

    async def test_white_attribute_writes_brightness_and_white_mode(self):
        light = self._light()
        light._attr_supported_color_modes = light._build_supported_color_modes()

        await light.async_turn_on(**{ATTR_WHITE: 128})

        self.assertEqual(
            light._device.states,
            {
                2: "white",
                3: light._ha_brightness_to_raw(128),
            },
        )

    def test_white_mode_requires_dedicated_brightness_dp(self):
        light = self._light()
        del light._config[CONF_BRIGHTNESS]

        self.assertEqual(
            light._build_supported_color_modes(),
            {ColorMode.HS},
        )


if __name__ == "__main__":
    unittest.main()
