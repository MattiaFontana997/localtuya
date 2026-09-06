from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"expected patch anchor missing in {path}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "custom_components/localtuya/const.py",
    'CONF_MAX_TEMP_DP = "max_temperature_dp"\nCONF_MIN_TEMP_DP = "min_temperature_dp"\nCONF_TEMP_MAX = "max_temperature_const"',
    'CONF_MAX_TEMP_DP = "max_temperature_dp"\nCONF_MIN_TEMP_DP = "min_temperature_dp"\nCONF_MAX_TEMP_PRECISION = "max_temperature_precision"\nCONF_MIN_TEMP_PRECISION = "min_temperature_precision"\nCONF_TEMP_MAX = "max_temperature_const"',
)

replace_once(
    "custom_components/localtuya/climate.py",
    "    CONF_MAX_TEMP_DP,\n    CONF_MIN_TEMP_DP,\n    CONF_PRECISION,",
    "    CONF_MAX_TEMP_DP,\n    CONF_MIN_TEMP_DP,\n    CONF_MAX_TEMP_PRECISION,\n    CONF_MIN_TEMP_PRECISION,\n    CONF_PRECISION,",
)

replace_once(
    "custom_components/localtuya/climate.py",
    "        self._current_humidity_precision = _positive_number(\n            self._config.get(CONF_CURRENT_HUMIDITY_PRECISION), 1.0\n        )\n        self._conf_hvac_mode_dp = self._config.get(CONF_HVAC_MODE_DP)",
    "        self._current_humidity_precision = _positive_number(\n            self._config.get(CONF_CURRENT_HUMIDITY_PRECISION), 1.0\n        )\n        self._min_temperature_precision = _positive_number(\n            self._config.get(CONF_MIN_TEMP_PRECISION), 1.0\n        )\n        self._max_temperature_precision = _positive_number(\n            self._config.get(CONF_MAX_TEMP_PRECISION), 1.0\n        )\n        self._conf_hvac_mode_dp = self._config.get(CONF_HVAC_MODE_DP)",
)

replace_once(
    "custom_components/localtuya/climate.py",
    "        if self.has_config(CONF_MIN_TEMP_DP):\n            value = self.dps_conf(CONF_MIN_TEMP_DP)\n            if isinstance(value, (int, float)) and not isinstance(value, bool):\n                return value\n        target_dp = self._active_target_temperature_dp()",
    "        if self.has_config(CONF_MIN_TEMP_DP):\n            value = self.dps_conf(CONF_MIN_TEMP_DP)\n            if isinstance(value, (int, float)) and not isinstance(value, bool):\n                return value * self._min_temperature_precision\n        target_dp = self._active_target_temperature_dp()",
)

replace_once(
    "custom_components/localtuya/climate.py",
    "        if self.has_config(CONF_MAX_TEMP_DP):\n            value = self.dps_conf(CONF_MAX_TEMP_DP)\n            if isinstance(value, (int, float)) and not isinstance(value, bool):\n                return value\n        target_dp = self._active_target_temperature_dp()",
    "        if self.has_config(CONF_MAX_TEMP_DP):\n            value = self.dps_conf(CONF_MAX_TEMP_DP)\n            if isinstance(value, (int, float)) and not isinstance(value, bool):\n                return value * self._max_temperature_precision\n        target_dp = self._active_target_temperature_dp()",
)

replace_once(
    "tests/test_climate_catalog_semantics.py",
    "    CONF_TARGET_TEMPERATURE_LOW_PRECISION, CONF_TARGET_TEMPERATURE_HIGH_PRECISION,\n)",
    "    CONF_TARGET_TEMPERATURE_LOW_PRECISION, CONF_TARGET_TEMPERATURE_HIGH_PRECISION,\n    CONF_MIN_TEMP_DP, CONF_MAX_TEMP_DP, CONF_MIN_TEMP_PRECISION, CONF_MAX_TEMP_PRECISION,\n)",
)

p = Path("tests/test_climate_catalog_semantics.py")
text = p.read_text(encoding="utf-8")
marker = "\n\nif __name__ == \"__main__\":\n"
test = '''\n    def test_dynamic_limit_dps_apply_independent_precision(self):\n        entity = self.bare({\n            "id": 1,\n            CONF_MIN_TEMP_DP: 26,\n            CONF_MAX_TEMP_DP: 19,\n            CONF_MIN_TEMP_PRECISION: 0.1,\n            CONF_MAX_TEMP_PRECISION: 0.1,\n        })\n        entity._min_temperature_precision = 0.1\n        entity._max_temperature_precision = 0.1\n        entity.dps_conf = lambda key: {CONF_MIN_TEMP_DP: 50, CONF_MAX_TEMP_DP: 350}[key]\n        self.assertEqual(entity.min_temp, 5.0)\n        self.assertEqual(entity.max_temp, 35.0)\n'''
if "test_dynamic_limit_dps_apply_independent_precision" not in text:
    if marker not in text:
        raise SystemExit("test insertion marker missing")
    p.write_text(text.replace(marker, test + marker, 1), encoding="utf-8")
