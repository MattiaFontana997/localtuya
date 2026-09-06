from pathlib import Path

fan = Path('custom_components/localtuya/fan.py')
text = fan.read_text(encoding='utf-8')

old = 'from .common import LocalTuyaEntity, async_setup_entry\nfrom .const import ('
new = '''from .common import LocalTuyaEntity, async_setup_entry
from .fan_mapping import (
    RAW_TYPES as FAN_RAW_TYPES,
    coerce_fan_raw,
    fan_oscillation_from_raw,
    fan_oscillation_to_raw,
    fan_speed_from_raw,
    fan_speed_to_raw,
    validate_fan_oscillation_mapping,
    validate_fan_speed_mapping,
)
from .const import ('''
if old not in text:
    raise SystemExit('fan import marker missing')
text = text.replace(old, new, 1)

old = '''        self._preset_values = self._configured_preset_values()\n        self._preset_raw_to_name = {\n            raw: name for name, raw in self._preset_values.items()\n        }'''
new = '''        self._preset_raw_type = self._config.get("fan_preset_raw_type", "string")
        if self._preset_raw_type not in FAN_RAW_TYPES:
            self.warning("Invalid fan preset raw type %r; disabling presets", self._preset_raw_type)
            self._preset_raw_type = "string"
        self._speed_mapping = validate_fan_speed_mapping(
            self._config.get("fan_speed_mapping")
        )
        self._oscillation_mapping = validate_fan_oscillation_mapping(
            self._config.get("fan_oscillating_mapping")
        )
        self._preset_values = self._configured_preset_values()
        self._preset_raw_to_name = {
            raw: name for name, raw in self._preset_values.items()
        }'''
if old not in text:
    raise SystemExit('fan preset init marker missing')
text = text.replace(old, new, 1)

old = '''        if self.has_config(CONF_FAN_SPEED_CONTROL):\n            if self._use_ordered_list:\n                self._attr_speed_count = len(self._ordered_list)\n            else:\n                self._attr_speed_count = int_states_in_range(\n                    self._speed_range\n                )'''
new = '''        if self.has_config(CONF_FAN_SPEED_CONTROL):
            if self._speed_mapping:
                self._attr_speed_count = len(self._speed_mapping["rules"])
            elif self._use_ordered_list:
                self._attr_speed_count = len(self._ordered_list)
            else:
                self._attr_speed_count = int_states_in_range(
                    self._speed_range
                )'''
if old not in text:
    raise SystemExit('fan speed count marker missing')
text = text.replace(old, new, 1)

start = text.index('    def _configured_preset_values(self)')
end = text.index('\n    @property\n    def is_on', start)
new_method = '''    def _configured_preset_values(self) -> dict[str, object]:
        """Return validated friendly -> typed raw fan presets."""
        configured = self._config.get(CONF_FAN_PRESET_VALUES)
        if configured is None:
            return {}
        if not isinstance(configured, dict):
            self.warning("Invalid fan_preset_values config; ignoring presets")
            return {}

        result: dict[str, object] = {}
        raw_values: list[object] = []
        for name, raw in configured.items():
            if not isinstance(name, str) or not name.strip():
                self.warning("Ignoring invalid fan preset %r: %r", name, raw)
                continue
            try:
                raw = coerce_fan_raw(raw, self._preset_raw_type)
            except ValueError:
                self.warning("Ignoring invalid fan preset %r: %r", name, raw)
                continue
            name = name.strip()
            if name in result or any(raw == previous for previous in raw_values):
                self.warning("Ignoring duplicate fan preset %r: %r", name, raw)
                continue
            result[name] = raw
            raw_values.append(raw)
        return result
'''
text = text[:start] + new_method + text[end:]

old = '''    def _percentage_to_raw(self, percentage: int):\n        """Convert an HA percentage to the configured Tuya speed."""\n        percentage = min(max(int(percentage), 1), 100)\n\n        if self._use_ordered_list:'''
new = '''    def _percentage_to_raw(self, percentage: int):
        """Convert an HA percentage to the configured Tuya speed."""
        percentage = min(max(int(percentage), 1), 100)

        if self._speed_mapping:
            return fan_speed_to_raw(percentage, self._speed_mapping)

        if self._use_ordered_list:'''
if old not in text:
    raise SystemExit('fan percentage to raw marker missing')
text = text.replace(old, new, 1)

old = '''        try:\n            if self._use_ordered_list:\n                return ordered_list_item_to_percentage('''
new = '''        try:
            if self._speed_mapping:
                return fan_speed_from_raw(raw_value, self._speed_mapping)

            if self._use_ordered_list:
                return ordered_list_item_to_percentage('''
if old not in text:
    raise SystemExit('fan raw to percentage marker missing')
text = text.replace(old, new, 1)

old = '''        await self._device.set_dp(\n            self._oscillating_on if oscillating else self._oscillating_off,\n            self._config[CONF_FAN_OSCILLATING_CONTROL],\n        )'''
new = '''        raw_value = (
            fan_oscillation_to_raw(oscillating, self._oscillation_mapping)
            if self._oscillation_mapping
            else (self._oscillating_on if oscillating else self._oscillating_off)
        )
        await self._device.set_dp(
            raw_value,
            self._config[CONF_FAN_OSCILLATING_CONTROL],
        )'''
if old not in text:
    raise SystemExit('fan oscillate write marker missing')
text = text.replace(old, new, 1)

old = '''        if self.has_config(CONF_FAN_OSCILLATING_CONTROL):\n            value = self.dps_conf(CONF_FAN_OSCILLATING_CONTROL)\n            if value == self._oscillating_on:\n                self._attr_oscillating = True\n            elif value == self._oscillating_off:\n                self._attr_oscillating = False\n            else:\n                self._attr_oscillating = None'''
new = '''        if self.has_config(CONF_FAN_OSCILLATING_CONTROL):
            value = self.dps_conf(CONF_FAN_OSCILLATING_CONTROL)
            if self._oscillation_mapping:
                self._attr_oscillating = fan_oscillation_from_raw(
                    value, self._oscillation_mapping
                )
            elif value == self._oscillating_on:
                self._attr_oscillating = True
            elif value == self._oscillating_off:
                self._attr_oscillating = False
            else:
                self._attr_oscillating = None'''
if old not in text:
    raise SystemExit('fan oscillate read marker missing')
text = text.replace(old, new, 1)
fan.write_text(text, encoding='utf-8')

catalog = Path('custom_components/localtuya/device_catalog.py')
text = catalog.read_text(encoding='utf-8')
old = '''    if "sensor_value_mapping" in config:\n        from .sensor_mapping import validate_sensor_value_mapping\n\n        mapping = validate_sensor_value_mapping(config["sensor_value_mapping"])'''
new = '''    if platform == "fan" and any(
        key in config
        for key in ("fan_speed_mapping", "fan_oscillating_mapping", "fan_preset_raw_type")
    ):
        from .fan_mapping import (
            RAW_TYPES as FAN_RAW_TYPES,
            coerce_fan_raw,
            validate_fan_oscillation_mapping,
            validate_fan_speed_mapping,
        )

        if "fan_speed_mapping" in config:
            mapping = validate_fan_speed_mapping(config["fan_speed_mapping"])
            if mapping is None or "fan_speed_control" not in config:
                return None
            config["fan_speed_mapping"] = mapping
        if "fan_oscillating_mapping" in config:
            mapping = validate_fan_oscillation_mapping(config["fan_oscillating_mapping"])
            if mapping is None or "fan_oscillating_control" not in config:
                return None
            config["fan_oscillating_mapping"] = mapping
        if "fan_preset_raw_type" in config:
            raw_type = config["fan_preset_raw_type"]
            values = config.get("fan_preset_values")
            if (
                raw_type not in FAN_RAW_TYPES
                or "fan_preset_dp" not in config
                or not isinstance(values, dict)
                or not values
                or len(values) > 32
            ):
                return None
            normalized_values = {}
            seen_raw = []
            for name, raw in values.items():
                if not isinstance(name, str) or not name.strip():
                    return None
                try:
                    raw = coerce_fan_raw(raw, raw_type)
                except ValueError:
                    return None
                name = name.strip()
                if name in normalized_values or any(raw == previous for previous in seen_raw):
                    return None
                normalized_values[name] = raw
                seen_raw.append(raw)
            config["fan_preset_values"] = normalized_values

    if "sensor_value_mapping" in config:
        from .sensor_mapping import validate_sensor_value_mapping

        mapping = validate_sensor_value_mapping(config["sensor_value_mapping"])'''
if old not in text:
    raise SystemExit('catalog fan validation insertion marker missing')
text = text.replace(old, new, 1)

old = '''        "effect": ("effect_values",), "fan_preset_dp": ("fan_preset_values",),\n        "fan_oscillating_control": ("fan_oscillating_on", "fan_oscillating_off"),'''
new = '''        "effect": ("effect_values",),
        "fan_speed_control": ("fan_speed_mapping", "fan_speed_ordered_list", "fan_dps_type", "fan_speed_min", "fan_speed_max"),
        "fan_preset_dp": ("fan_preset_values", "fan_preset_raw_type"),
        "fan_oscillating_control": ("fan_oscillating_on", "fan_oscillating_off", "fan_oscillating_mapping"),'''
if old not in text:
    raise SystemExit('catalog fan dependent marker missing')
text = text.replace(old, new, 1)
catalog.write_text(text, encoding='utf-8')
