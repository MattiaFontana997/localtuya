"""Regression tests for catalog-provided Tuya light scenes."""

from __future__ import annotations

import unittest

from homeassistant.const import CONF_SCENE

from custom_components.localtuya.const import CONF_SCENE_VALUES
from custom_components.localtuya.light import LocaltuyaLight, Mode


class LightSceneValuesTests(unittest.TestCase):
    @staticmethod
    def _light(config):
        light = object.__new__(LocaltuyaLight)
        light._config = config
        light._modes = Mode()
        light.warning = lambda *args, **kwargs: None
        return light

    def test_payload_scenes_are_preserved_with_scene_dp(self):
        light = self._light(
            {
                CONF_SCENE: 25,
                CONF_SCENE_VALUES: {
                    "Reading": "010e0d0000840000000003e801f4",
                    "Rainbow": "05464601000003e8",
                },
            }
        )

        self.assertEqual(
            light._configured_scenes(),
            {
                "Reading": "010e0d0000840000000003e801f4",
                "Rainbow": "05464601000003e8",
            },
        )

    def test_mode_only_scenes_do_not_require_scene_dp(self):
        light = self._light(
            {
                CONF_SCENE_VALUES: {
                    "Scenario 1": "scene_1",
                    "Scenario 4": "scene_4",
                }
            }
        )

        self.assertEqual(
            light._configured_scenes(),
            {
                "Scenario 1": "scene_1",
                "Scenario 4": "scene_4",
            },
        )

    def test_bare_scene_mode_reads_back_without_scene_dp(self):
        light = self._light(
            {
                CONF_SCENE_VALUES: {
                    "Scene": "scene",
                }
            }
        )
        light._scenes = light._configured_scenes()

        self.assertEqual(light._scenes, {"Scene": "scene"})
        self.assertEqual(light._find_scene_by_scene_data(None), "Scene")

    def test_payload_scene_without_scene_dp_is_ignored(self):
        light = self._light(
            {
                CONF_SCENE_VALUES: {
                    "Reading": "010e0d0000840000000003e801f4",
                    "Scenario 1": "scene_1",
                }
            }
        )

        self.assertEqual(
            light._configured_scenes(),
            {"Scenario 1": "scene_1"},
        )

    def test_invalid_scene_values_fall_back_to_empty(self):
        light = self._light({CONF_SCENE_VALUES: ["scene_1"]})

        self.assertEqual(light._configured_scenes(), {})


if __name__ == "__main__":
    unittest.main()
