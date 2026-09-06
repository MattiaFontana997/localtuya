from pathlib import Path


def replace_once(path, old, new, label):
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'{label} marker missing in {path}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


# advanced_mapping.py: expose active numeric metadata, prefer requested
# condition on writes, and enforce active ranges.
p = Path('custom_components/localtuya/advanced_mapping.py')
text = p.read_text(encoding='utf-8')
marker = '''def map_value_from_dps(raw: Any, rules: list[dict[str, Any]], status: dict[str, Any]) -> tuple[Any, int | None]:\n'''
insert = '''def effective_mapping_metadata(\n    raw: Any, rules: list[dict[str, Any]], status: dict[str, Any]\n) -> dict[str, Any]:\n    \"\"\"Return bounded numeric metadata for the currently active mapping.\"\"\"\n    rule = _find_rule_for_raw(rules, raw)\n    if rule is None:\n        return {}\n    active = _active_condition(rule, status)\n    effective = dict(rule)\n    if active:\n        effective.update({key: value for key, value in active.items() if key != \"dps_val\"})\n    return {\n        key: effective[key]\n        for key in (\"range\", \"target_range\", \"step\", \"scale\")\n        if key in effective\n    }\n\n\ndef _condition_for_requested_value(rule: dict[str, Any], value: Any) -> dict[str, Any] | None:\n    \"\"\"Match Tuya Local's write-time condition selection semantics.\"\"\"\n    for condition in rule.get(\"conditions\", []):\n        if \"value\" in condition and _matches(condition[\"value\"], value):\n            return condition\n    return None\n\n\n'''
if marker not in text:
    raise SystemExit('advanced metadata marker missing')
text = text.replace(marker, insert + marker, 1)
old = '''    active = _active_condition(rule, status)\n    effective = dict(rule)\n    if active:\n        effective.update({key: item for key, item in active.items() if key != \"dps_val\"})\n    if effective.get(\"invalid\", False):\n        raise ValueError(\"Value is invalid for the active advanced mapping\")\n    result = _transform_numeric(effective.get(\"dps_val\", value), effective, reverse=True)\n    target_dp = int(effective.get(\"value_redirect_dp\", primary_dp))\n'''
new = '''    active = _condition_for_requested_value(rule, value) or _active_condition(rule, status)\n    effective = dict(rule)\n    if active:\n        effective.update({key: item for key, item in active.items() if key != \"dps_val\"})\n    if effective.get(\"invalid\", False):\n        raise ValueError(\"Value is invalid for the active advanced mapping\")\n    result = _transform_numeric(effective.get(\"dps_val\", value), effective, reverse=True)\n    active_range = effective.get(\"range\")\n    if active_range is not None and isinstance(result, (int, float)) and not isinstance(result, bool):\n        minimum = float(active_range[\"min\"])\n        maximum = float(active_range[\"max\"])\n        if float(result) < minimum or float(result) > maximum:\n            raise ValueError(\"Value is outside the active advanced mapping range\")\n    target_dp = int(effective.get(\"value_redirect_dp\", primary_dp))\n'''
if old not in text:
    raise SystemExit('reverse mapping marker missing')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# common.py: expose current effective metadata to platforms.
replace_once(
    'custom_components/localtuya/common.py',
    '    advanced_mapping_dp_references,\n    map_value_from_dps,\n',
    '    advanced_mapping_dp_references,\n    effective_mapping_metadata,\n    map_value_from_dps,\n',
    'common import',
)
replace_once(
    'custom_components/localtuya/common.py',
    '''    def has_advanced_mapping(self, dp_index=None):\n        \"\"\"Return whether one logical DP has a declarative catalog mapping.\"\"\"\n        dp_index = self._dp_id if dp_index is None else dp_index\n        return bool(self._mapping_for_dp(dp_index))\n\n''',
    '''    def has_advanced_mapping(self, dp_index=None):\n        \"\"\"Return whether one logical DP has a declarative catalog mapping.\"\"\"\n        dp_index = self._dp_id if dp_index is None else dp_index\n        return bool(self._mapping_for_dp(dp_index))\n\n    def mapped_numeric_metadata(self, dp_index=None):\n        \"\"\"Return active declarative range/step metadata for one logical DP.\"\"\"\n        dp_index = self._dp_id if dp_index is None else dp_index\n        rules = self._mapping_for_dp(dp_index)\n        if not rules:\n            return {}\n        raw = self.raw_dps(dp_index)\n        return effective_mapping_metadata(raw, rules, self._status)\n\n''',
    'common metadata method',
)

# climate.py: dynamic target ranges/steps mirror active Tuya Local conditions.
replace_once(
    'custom_components/localtuya/climate.py',
    '''    @property\n    def target_temperature_step(self):\n        \"\"\"Return the supported step of target temperature.\"\"\"\n        return self._config.get(CONF_TEMPERATURE_STEP, DEFAULT_TEMPERATURE_STEP)\n''',
    '''    @property\n    def target_temperature_step(self):\n        \"\"\"Return the supported step of the active target-temperature mapping.\"\"\"\n        target_dp = self._active_target_temperature_dp()\n        if target_dp is not None:\n            metadata = self.mapped_numeric_metadata(target_dp)\n            step = metadata.get(\"step\")\n            if isinstance(step, (int, float)) and not isinstance(step, bool) and step > 0:\n                return float(step) * self._target_precision\n        return self._config.get(CONF_TEMPERATURE_STEP, DEFAULT_TEMPERATURE_STEP)\n''',
    'climate step',
)
replace_once(
    'custom_components/localtuya/climate.py',
    '''    @property\n    def min_humidity(self):\n        return self._config.get(CONF_HUMIDITY_MIN, DEFAULT_MIN_HUMIDITY)\n\n    @property\n    def max_humidity(self):\n        return self._config.get(CONF_HUMIDITY_MAX, DEFAULT_MAX_HUMIDITY)\n''',
    '''    @property\n    def min_humidity(self):\n        dp = self._config.get(CONF_TARGET_HUMIDITY_DP)\n        metadata = self.mapped_numeric_metadata(dp) if dp is not None else {}\n        value_range = metadata.get(\"range\")\n        if isinstance(value_range, dict) and \"min\" in value_range:\n            return float(value_range[\"min\"]) * self._target_humidity_precision\n        return self._config.get(CONF_HUMIDITY_MIN, DEFAULT_MIN_HUMIDITY)\n\n    @property\n    def max_humidity(self):\n        dp = self._config.get(CONF_TARGET_HUMIDITY_DP)\n        metadata = self.mapped_numeric_metadata(dp) if dp is not None else {}\n        value_range = metadata.get(\"range\")\n        if isinstance(value_range, dict) and \"max\" in value_range:\n            return float(value_range[\"max\"]) * self._target_humidity_precision\n        return self._config.get(CONF_HUMIDITY_MAX, DEFAULT_MAX_HUMIDITY)\n''',
    'climate humidity metadata',
)
replace_once(
    'custom_components/localtuya/climate.py',
    '''    @property\n    def min_temp(self):\n        \"\"\"Return the minimum target temperature.\"\"\"\n        if self.has_config(CONF_MIN_TEMP_DP):\n            value = self.dps_conf(CONF_MIN_TEMP_DP)\n            if isinstance(value, (int, float)) and not isinstance(value, bool):\n                return value\n\n        return self._config.get(CONF_TEMP_MIN, DEFAULT_MIN_TEMP)\n\n    @property\n    def max_temp(self):\n        \"\"\"Return the maximum target temperature.\"\"\"\n        if self.has_config(CONF_MAX_TEMP_DP):\n            value = self.dps_conf(CONF_MAX_TEMP_DP)\n            if isinstance(value, (int, float)) and not isinstance(value, bool):\n                return value\n\n        return self._config.get(CONF_TEMP_MAX, DEFAULT_MAX_TEMP)\n''',
    '''    @property\n    def min_temp(self):\n        \"\"\"Return the minimum target temperature for the active mapping.\"\"\"\n        if self.has_config(CONF_MIN_TEMP_DP):\n            value = self.dps_conf(CONF_MIN_TEMP_DP)\n            if isinstance(value, (int, float)) and not isinstance(value, bool):\n                return value\n        target_dp = self._active_target_temperature_dp()\n        metadata = self.mapped_numeric_metadata(target_dp) if target_dp is not None else {}\n        value_range = metadata.get(\"range\")\n        if isinstance(value_range, dict) and \"min\" in value_range:\n            return float(value_range[\"min\"]) * self._target_precision\n        return self._config.get(CONF_TEMP_MIN, DEFAULT_MIN_TEMP)\n\n    @property\n    def max_temp(self):\n        \"\"\"Return the maximum target temperature for the active mapping.\"\"\"\n        if self.has_config(CONF_MAX_TEMP_DP):\n            value = self.dps_conf(CONF_MAX_TEMP_DP)\n            if isinstance(value, (int, float)) and not isinstance(value, bool):\n                return value\n        target_dp = self._active_target_temperature_dp()\n        metadata = self.mapped_numeric_metadata(target_dp) if target_dp is not None else {}\n        value_range = metadata.get(\"range\")\n        if isinstance(value_range, dict) and \"max\" in value_range:\n            return float(value_range[\"max\"]) * self._target_precision\n        return self._config.get(CONF_TEMP_MAX, DEFAULT_MAX_TEMP)\n''',
    'climate range metadata',
)

# number.py: expose active condition ranges/steps through HA properties.
replace_once(
    'custom_components/localtuya/number.py',
    '''    @property\n    def native_value(self) -> float | None:\n        return self._state\n''',
    '''    @property\n    def native_value(self) -> float | None:\n        return self._state\n\n    @property\n    def native_min_value(self) -> float:\n        metadata = self.mapped_numeric_metadata(self._dp_id)\n        value_range = metadata.get(\"range\")\n        if isinstance(value_range, dict) and \"min\" in value_range:\n            return float(value_range[\"min\"]) * self._scaling\n        return self._attr_native_min_value\n\n    @property\n    def native_max_value(self) -> float:\n        metadata = self.mapped_numeric_metadata(self._dp_id)\n        value_range = metadata.get(\"range\")\n        if isinstance(value_range, dict) and \"max\" in value_range:\n            return float(value_range[\"max\"]) * self._scaling\n        return self._attr_native_max_value\n\n    @property\n    def native_step(self) -> float:\n        metadata = self.mapped_numeric_metadata(self._dp_id)\n        step = metadata.get(\"step\")\n        if isinstance(step, (int, float)) and not isinstance(step, bool) and step > 0:\n            return float(step) * self._scaling\n        return self._attr_native_step\n''',
    'number metadata properties',
)

# water_heater.py: dynamic range/step for condition-selected units/redirects.
replace_once(
    'custom_components/localtuya/water_heater.py',
    '''    @property\n    def target_temperature_step(self):\n        \"\"\"Return target temperature step.\"\"\"\n        return self._temp_step\n''',
    '''    @property\n    def target_temperature_step(self):\n        \"\"\"Return target temperature step for the active mapping.\"\"\"\n        dp_id = self._config.get(CONF_WATER_HEATER_TARGET_TEMPERATURE_DP)\n        metadata = self.mapped_numeric_metadata(dp_id) if dp_id is not None else {}\n        step = metadata.get(\"step\")\n        if isinstance(step, (int, float)) and not isinstance(step, bool) and step > 0:\n            return float(step) * self._scaling\n        return self._temp_step\n''',
    'water heater step',
)
replace_once(
    'custom_components/localtuya/water_heater.py',
    '''    @property\n    def min_temp(self):\n        \"\"\"Return minimum target temperature.\"\"\"\n        dp_id = self._config.get(CONF_WATER_HEATER_MIN_TEMPERATURE_DP)\n        value = _scaled(self.dps(dp_id), self._scaling) if dp_id is not None else None\n        return value if value is not None else self._temp_min\n\n    @property\n    def max_temp(self):\n        \"\"\"Return maximum target temperature.\"\"\"\n        dp_id = self._config.get(CONF_WATER_HEATER_MAX_TEMPERATURE_DP)\n        value = _scaled(self.dps(dp_id), self._scaling) if dp_id is not None else None\n        return value if value is not None else self._temp_max\n''',
    '''    @property\n    def min_temp(self):\n        \"\"\"Return minimum target temperature for the active mapping.\"\"\"\n        dp_id = self._config.get(CONF_WATER_HEATER_MIN_TEMPERATURE_DP)\n        value = _scaled(self.dps(dp_id), self._scaling) if dp_id is not None else None\n        if value is not None:\n            return value\n        target_dp = self._config.get(CONF_WATER_HEATER_TARGET_TEMPERATURE_DP)\n        metadata = self.mapped_numeric_metadata(target_dp) if target_dp is not None else {}\n        value_range = metadata.get(\"range\")\n        if isinstance(value_range, dict) and \"min\" in value_range:\n            return float(value_range[\"min\"]) * self._scaling\n        return self._temp_min\n\n    @property\n    def max_temp(self):\n        \"\"\"Return maximum target temperature for the active mapping.\"\"\"\n        dp_id = self._config.get(CONF_WATER_HEATER_MAX_TEMPERATURE_DP)\n        value = _scaled(self.dps(dp_id), self._scaling) if dp_id is not None else None\n        if value is not None:\n            return value\n        target_dp = self._config.get(CONF_WATER_HEATER_TARGET_TEMPERATURE_DP)\n        metadata = self.mapped_numeric_metadata(target_dp) if target_dp is not None else {}\n        value_range = metadata.get(\"range\")\n        if isinstance(value_range, dict) and \"max\" in value_range:\n            return float(value_range[\"max\"]) * self._scaling\n        return self._temp_max\n''',
    'water heater range',
)

# Permanent regression coverage.
Path('tests/test_advanced_mapping_v2.py').write_text(r'''"""Batch M advanced mapping v2 runtime regressions."""

import unittest

from custom_components.localtuya.advanced_mapping import (
    effective_mapping_metadata,
    map_value_from_dps,
    map_value_to_dps,
)


class AdvancedMappingV2Tests(unittest.TestCase):
    def test_condition_range_and_step_are_active_metadata(self):
        rules = [{
            "constraint_dp": 19,
            "conditions": [{
                "dps_val": "f",
                "range": {"min": 410, "max": 950},
                "step": 10,
            }],
        }]
        self.assertEqual(
            effective_mapping_metadata(700, rules, {"19": "f"}),
            {"range": {"min": 410.0, "max": 950.0}, "step": 10.0},
        )
        self.assertEqual(effective_mapping_metadata(200, rules, {"19": "c"}), {})

    def test_active_range_rejects_out_of_range_write(self):
        rules = [{
            "constraint_dp": 19,
            "conditions": [{
                "dps_val": "f",
                "range": {"min": 410, "max": 950},
                "step": 10,
            }],
        }]
        self.assertEqual(map_value_to_dps(723, rules, {"19": "f"}, 2), {2: 720})
        with self.assertRaises(ValueError):
            map_value_to_dps(300, rules, {"19": "f"}, 2)

    def test_requested_condition_wins_during_reverse_mapping(self):
        rules = [{
            "dps_val": True,
            "constraint_dp": 4,
            "conditions": [
                {"dps_val": "cold", "value": "cool"},
                {"dps_val": "hot", "value": "heat"},
            ],
        }]
        self.assertEqual(
            map_value_to_dps("heat", rules, {"4": "cold"}, 1),
            {1: True, 4: "hot"},
        )

    def test_condition_scale_is_applied_on_read(self):
        rules = [{
            "constraint_dp": 111,
            "conditions": [
                {"dps_val": "0", "scale": 10},
                {"dps_val": "1", "value_redirect_dp": 106},
            ],
        }]
        self.assertEqual(map_value_from_dps(235, rules, {"111": "0"}), (23.5, None))
        self.assertEqual(map_value_from_dps(235, rules, {"111": "1"}), (235, 106))


if __name__ == "__main__":
    unittest.main()
''', encoding='utf-8')
