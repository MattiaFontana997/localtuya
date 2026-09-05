"""Regression tests for dedicated Tuya light effect values."""

from __future__ import annotations

import unittest

from custom_components.localtuya.const import CONF_EFFECT, CONF_EFFECT_VALUES
from custom_components.localtuya.light import LocaltuyaLight


class LightEffectValuesTests(unittest.TestCase):
    @staticmethod
    def _light(config):
        light = object.__new__(LocaltuyaLight)
        light._config = config
        light.warning = lambda *args, **kwargs: None
        return light

    def test_exact_dedicated_effect_values_are_preserved(self):
        light = self._light(
            {
                CONF_EFFECT: 104,
                CONF_EFFECT_VALUES: {
                    "Combination": "1",
                    "In Wave": "2",
                    "Steady": "8",
                },
            }
        )

        self.assertEqual(
            light._configured_effects(),
            {
                "Combination": "1",
                "In Wave": "2",
                "Steady": "8",
            },
        )

    def test_effect_values_require_effect_dp(self):
        light = self._light(
            {CONF_EFFECT_VALUES: {"Combination": "1"}}
        )

        self.assertEqual(light._configured_effects(), {})

    def test_dedicated_effects_take_precedence_over_scene_modes(self):
        light = self._light({})
        light._effects = {"Combination": "1", "Steady": "8"}
        light._scenes = {"Rainbow": "scene_1"}
        light._music_mode_enabled = True

        self.assertEqual(
            light._build_effect_list(),
            ["Combination", "Steady"],
        )

    def test_raw_effect_value_decodes_to_friendly_name(self):
        light = self._light({})
        light._effects = {"Combination": "1", "Steady": "8"}

        self.assertEqual(light._find_effect_by_raw("8"), "Steady")
        self.assertIsNone(light._find_effect_by_raw("9"))

    def test_invalid_or_duplicate_raw_values_are_ignored(self):
        light = self._light(
            {
                CONF_EFFECT: 104,
                CONF_EFFECT_VALUES: {
                    "Combination": "1",
                    "Duplicate": "1",
                    "": "2",
                    "Invalid": 3,
                },
            }
        )

        self.assertEqual(
            light._configured_effects(),
            {"Combination": "1"},
        )


if __name__ == "__main__":
    unittest.main()
