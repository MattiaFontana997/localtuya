from pathlib import Path

path = Path('custom_components/localtuya/fan.py')
text = path.read_text(encoding='utf-8')

old = '''        result: dict[str, object] = {}\n        raw_values: list[object] = []\n        for name, raw in configured.items():'''
new = '''        raw_type = getattr(\n            self,\n            "_preset_raw_type",\n            self._config.get("fan_preset_raw_type", "string"),\n        )\n        if raw_type not in FAN_RAW_TYPES:\n            raw_type = "string"\n\n        result: dict[str, object] = {}\n        raw_values: list[object] = []\n        for name, raw in configured.items():'''
if old not in text:
    raise SystemExit('preset fallback marker missing')
text = text.replace(old, new, 1)

old = '                raw = coerce_fan_raw(raw, self._preset_raw_type)'
new = '                raw = coerce_fan_raw(raw, raw_type)'
if old not in text:
    raise SystemExit('preset coercion marker missing')
text = text.replace(old, new, 1)

old = '''        raw_value = (\n            fan_oscillation_to_raw(oscillating, self._oscillation_mapping)\n            if self._oscillation_mapping\n            else (self._oscillating_on if oscillating else self._oscillating_off)\n        )'''
new = '''        oscillation_mapping = getattr(self, "_oscillation_mapping", None)\n        raw_value = (\n            fan_oscillation_to_raw(oscillating, oscillation_mapping)\n            if oscillation_mapping\n            else (self._oscillating_on if oscillating else self._oscillating_off)\n        )'''
if old not in text:
    raise SystemExit('oscillation write fallback marker missing')
text = text.replace(old, new, 1)

old = '''        if self.has_config(CONF_FAN_OSCILLATING_CONTROL):\n            value = self.dps_conf(CONF_FAN_OSCILLATING_CONTROL)\n            if self._oscillation_mapping:\n                self._attr_oscillating = fan_oscillation_from_raw(\n                    value, self._oscillation_mapping\n                )'''
new = '''        if self.has_config(CONF_FAN_OSCILLATING_CONTROL):\n            value = self.dps_conf(CONF_FAN_OSCILLATING_CONTROL)\n            oscillation_mapping = getattr(self, "_oscillation_mapping", None)\n            if oscillation_mapping:\n                self._attr_oscillating = fan_oscillation_from_raw(\n                    value, oscillation_mapping\n                )'''
if old not in text:
    raise SystemExit('oscillation read fallback marker missing')
text = text.replace(old, new, 1)

path.write_text(text, encoding='utf-8')
