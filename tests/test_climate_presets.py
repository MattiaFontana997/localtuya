"""Regression tests for LocalTuya climate preset mappings."""

import unittest
from types import SimpleNamespace

from homeassistant.components.climate.const import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    PRESET_NONE,
)

from custom_components.localtuya.climate import (
    LocaltuyaClimate,
    PRESET_SETS,
)
from custom_components.localtuya.const import (
    CONF_AWAY_TEMPERATURE_DP,
    CONF_TARGET_TEMPERATURE_DP,
)


THERMOSTAT_PRESET_SET = (
    "auto/manual/temporary/boost/holiday"
)


class ClimatePresetTests(unittest.TestCase):
    """Test thermostat preset semantics."""

    def test_extended_thermostat_presets(self):
        presets = PRESET_SETS[
            THERMOSTAT_PRESET_SET
        ]

        self.assertEqual(
            presets["auto"],
            "auto",
        )
        self.assertEqual(
            presets[PRESET_HOME],
            "manual",
        )
        self.assertEqual(
            presets["temporary"],
            "temporary",
        )
        self.assertEqual(
            presets[PRESET_BOOST],
            "boost",
        )
        self.assertEqual(
            presets[PRESET_AWAY],
            "holiday",
        )

        self.assertNotIn(
            PRESET_NONE,
            presets,
        )

    def test_normal_preset_uses_normal_target_dp(self):
        climate = SimpleNamespace(
            _config={
                CONF_TARGET_TEMPERATURE_DP: 16,
                CONF_AWAY_TEMPERATURE_DP: 32,
            },
            _conf_preset_dp=2,
            _conf_preset_set={
                PRESET_AWAY: "holiday",
            },
            dps=lambda dp: (
                "manual"
                if dp == 2
                else None
            ),
        )

        target_dp = (
            LocaltuyaClimate
            ._active_target_temperature_dp(
                climate
            )
        )

        self.assertEqual(
            target_dp,
            16,
        )

    def test_away_preset_uses_away_target_dp(self):
        climate = SimpleNamespace(
            _config={
                CONF_TARGET_TEMPERATURE_DP: 16,
                CONF_AWAY_TEMPERATURE_DP: 32,
            },
            _conf_preset_dp=2,
            _conf_preset_set={
                PRESET_AWAY: "holiday",
            },
            dps=lambda dp: (
                "holiday"
                if dp == 2
                else None
            ),
        )

        target_dp = (
            LocaltuyaClimate
            ._active_target_temperature_dp(
                climate
            )
        )

        self.assertEqual(
            target_dp,
            32,
        )


if __name__ == "__main__":
    unittest.main()
