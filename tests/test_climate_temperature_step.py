"""Regression tests for arbitrary positive climate target-temperature steps."""

import unittest

import voluptuous as vol

from custom_components.localtuya.climate import LocaltuyaClimate, flow_schema
from custom_components.localtuya.const import (
    CONF_TARGET_PRECISION,
    CONF_TARGET_TEMPERATURE_DP,
    CONF_TEMPERATURE_STEP,
)
from custom_components.localtuya.device_mapper import build_entity_candidates


class ClimateTemperatureStepTests(unittest.TestCase):
    """Preserve the real Tuya target-temperature increment end to end."""

    def test_flow_schema_accepts_nonstandard_positive_step(self):
        schema = vol.Schema(flow_schema([1, 16, 24]))
        validated = schema({CONF_TEMPERATURE_STEP: 0.2})
        self.assertEqual(validated[CONF_TEMPERATURE_STEP], 0.2)

    def test_flow_schema_rejects_nonpositive_step(self):
        schema = vol.Schema(flow_schema([1, 16, 24]))
        with self.assertRaises(vol.Invalid):
            schema({CONF_TEMPERATURE_STEP: 0})
        with self.assertRaises(vol.Invalid):
            schema({CONF_TEMPERATURE_STEP: -0.2})

    def test_runtime_uses_mapped_nonstandard_step(self):
        climate = object.__new__(LocaltuyaClimate)
        climate._config = {
            CONF_TARGET_TEMPERATURE_DP: 16,
            CONF_TARGET_PRECISION: 0.1,
        }
        climate._target_precision = 0.1
        climate._conf_preset_dp = None
        climate._conf_preset_set = {}
        climate.mapped_numeric_metadata = lambda dp: {"step": 2}

        self.assertEqual(climate.target_temperature_step, 0.2)

    def test_mapper_preserves_nonstandard_scaled_step(self):
        device = {
            "name": "Fine Step Thermostat",
            "category": "wk",
        }
        specification = {
            "functions": [
                {
                    "dp_id": 1,
                    "code": "switch",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 16,
                    "code": "temp_set",
                    "type": "Integer",
                    "values": (
                        '{"unit":"℃","min":50,"max":350,'
                        '"scale":1,"step":2}'
                    ),
                },
            ],
            "status": [
                {
                    "dp_id": 1,
                    "code": "switch",
                    "type": "Boolean",
                    "values": "{}",
                },
                {
                    "dp_id": 16,
                    "code": "temp_set",
                    "type": "Integer",
                    "values": (
                        '{"unit":"℃","min":50,"max":350,'
                        '"scale":1,"step":2}'
                    ),
                },
                {
                    "dp_id": 24,
                    "code": "temp_current",
                    "type": "Integer",
                    "values": (
                        '{"unit":"℃","min":0,"max":400,'
                        '"scale":1,"step":1}'
                    ),
                },
            ],
        }

        candidates = build_entity_candidates(
            device,
            specification,
            available_dps={1, 16, 24},
        )
        climate = next(
            candidate for candidate in candidates
            if candidate.platform == "climate" and candidate.primary_dp == 1
        )

        self.assertEqual(climate.config["target_precision"], 0.1)
        self.assertEqual(climate.config["temperature_step"], 0.2)


if __name__ == "__main__":
    unittest.main()
