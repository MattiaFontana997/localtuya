"""Regression tests for LocalTuya climate preset mappings."""

import unittest

from homeassistant.components.climate.const import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    PRESET_NONE,
)

from custom_components.localtuya.climate import PRESET_SETS


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

        # Device "auto" is a real preset and must
        # not appear as HA's generic "none".
        self.assertNotIn(
            PRESET_NONE,
            presets,
        )


if __name__ == "__main__":
    unittest.main()
