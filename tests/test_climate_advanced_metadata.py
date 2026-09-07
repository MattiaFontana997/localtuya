"""Regression tests for conditional climate mapping metadata."""

import inspect
import unittest

from custom_components.localtuya.const import (
    CONF_TARGET_PRECISION, CONF_TARGET_TEMPERATURE_DP, CONF_TEMP_MAX, CONF_TEMP_MIN,
)
from custom_components.localtuya.climate import LocaltuyaClimate


class ClimateAdvancedMetadataTests(unittest.TestCase):
    @staticmethod
    def _bare(metadata):
        climate = object.__new__(LocaltuyaClimate)
        climate._config = {
            CONF_TARGET_TEMPERATURE_DP: 2,
            CONF_TARGET_PRECISION: 0.1,
            CONF_TEMP_MIN: 5.0,
            CONF_TEMP_MAX: 40.0,
        }
        climate._target_precision = 0.1
        climate._conf_preset_dp = None
        climate._conf_preset_set = {}
        climate.mapped_numeric_metadata = lambda dp: metadata
        return climate

    def test_conditional_range_updates_ha_min_max(self):
        climate = self._bare({"range": {"min": 410, "max": 1040}, "step": 10})
        self.assertEqual(climate.min_temp, 41.0)
        self.assertEqual(climate.max_temp, 104.0)
        self.assertEqual(climate.target_temperature_step, 1.0)

    def test_temperature_limit_properties_are_defined_once(self):
        source = inspect.getsource(LocaltuyaClimate)
        self.assertEqual(source.count("def min_temp(self):"), 1)
        self.assertEqual(source.count("def max_temp(self):"), 1)

    def test_static_fallback_remains_unchanged(self):
        climate = self._bare({})
        self.assertEqual(climate.min_temp, 5.0)
        self.assertEqual(climate.max_temp, 40.0)


if __name__ == "__main__":
    unittest.main()
