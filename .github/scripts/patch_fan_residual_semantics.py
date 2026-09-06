from pathlib import Path

const = Path('custom_components/localtuya/const.py')
text = const.read_text()
anchor = 'CONF_FAN_PRESET_VALUES = "fan_preset_values"\n'
insert = anchor + 'CONF_FAN_PRESET_DEFAULT = "fan_preset_default"\nCONF_FAN_NO_SWITCH = "fan_no_switch"\n'
if text.count(anchor) != 1:
    raise SystemExit(f'fan const anchor count={text.count(anchor)}')
const.write_text(text.replace(anchor, insert, 1))

fan = Path('custom_components/localtuya/fan.py')
text = fan.read_text()
old = '''    CONF_FAN_PRESET_DP,
    CONF_FAN_PRESET_VALUES,
    CONF_FAN_SPEED_CONTROL,
'''
new = '''    CONF_FAN_PRESET_DEFAULT,
    CONF_FAN_PRESET_DP,
    CONF_FAN_PRESET_VALUES,
    CONF_FAN_NO_SWITCH,
    CONF_FAN_SPEED_CONTROL,
'''
if text.count(old) != 1:
    raise SystemExit(f'fan const import anchor count={text.count(old)}')
text = text.replace(old, new, 1)
old = '''        vol.Optional(
            CONF_FAN_DPS_TYPE,
            default="str",
        ): vol.In(["str", "int"]),
'''
new = '''        vol.Optional(
            CONF_FAN_DPS_TYPE,
            default="str",
        ): vol.In(["str", "int"]),
        vol.Optional(CONF_FAN_NO_SWITCH, default=False): bool,
'''
if text.count(old) != 1:
    raise SystemExit(f'fan schema anchor count={text.count(old)}')
text = text.replace(old, new, 1)
old = '''        self._preset_values = self._configured_preset_values()
        self._preset_raw_to_name = {
            raw: name for name, raw in self._preset_values.items()
        }
'''
new = '''        self._preset_values = self._configured_preset_values()
        self._preset_default = self._config.get(CONF_FAN_PRESET_DEFAULT)
        if self._preset_default not in self._preset_values:
            self._preset_default = None
        self._preset_raw_to_name = {
            raw: name for name, raw in self._preset_values.items()
        }
        self._no_switch = self._config.get(CONF_FAN_NO_SWITCH) is True
'''
if text.count(old) != 1:
    raise SystemExit(f'fan init preset anchor count={text.count(old)}')
text = text.replace(old, new, 1)
old = '''        features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF

        if self.has_config(CONF_FAN_SPEED_CONTROL):
'''
new = '''        features = FanEntityFeature(0)
        if not self._no_switch:
            features |= FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF

        if self.has_config(CONF_FAN_SPEED_CONTROL):
'''
if text.count(old) != 1:
    raise SystemExit(f'fan feature anchor count={text.count(old)}')
text = text.replace(old, new, 1)
old = '''        states = {
            self._dp_id: True,
        }
'''
new = '''        states = {} if self._no_switch else {self._dp_id: True}
'''
if text.count(old) != 1:
    raise SystemExit(f'fan turn on states anchor count={text.count(old)}')
text = text.replace(old, new, 1)
old = '''    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the fan."""
        await self._device.set_dp(
            False,
            self._dp_id,
        )
'''
new = '''    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the fan."""
        if self._no_switch:
            raise NotImplementedError("This fan has no power control")
        await self._device.set_dp(
            False,
            self._dp_id,
        )
'''
if text.count(old) != 1:
    raise SystemExit(f'fan turn off anchor count={text.count(old)}')
text = text.replace(old, new, 1)
old = '''        if self.is_on is not True:
            states[self._dp_id] = True
'''
new = '''        if self.is_on is not True and not self._no_switch:
            states[self._dp_id] = True
'''
if text.count(old) != 1:
    raise SystemExit(f'fan percentage power anchor count={text.count(old)}')
text = text.replace(old, new, 1)
old = '''        raw_power = self._state

        if isinstance(raw_power, bool):
            self._is_on = raw_power
        elif raw_power in (0, 1):
            self._is_on = bool(raw_power)
        else:
            self._is_on = None
'''
new = '''        raw_power = self._state

        if self._no_switch:
            # Tuya Local models a fan without a switch as on whenever its
            # entity is available; HA availability already gates visibility.
            self._is_on = True
        elif isinstance(raw_power, bool):
            self._is_on = raw_power
        elif raw_power in (0, 1):
            self._is_on = bool(raw_power)
        else:
            self._is_on = None
'''
if text.count(old) != 1:
    raise SystemExit(f'fan status power anchor count={text.count(old)}')
text = text.replace(old, new, 1)
old = '''        if self.has_config(CONF_FAN_PRESET_DP):
            raw_preset = self.dps_conf(CONF_FAN_PRESET_DP)
            self._attr_preset_mode = self._preset_raw_to_name.get(raw_preset)
        else:
            self._attr_preset_mode = None
'''
new = '''        if self.has_config(CONF_FAN_PRESET_DP):
            raw_preset = self.dps_conf(CONF_FAN_PRESET_DP)
            self._attr_preset_mode = self._preset_raw_to_name.get(
                raw_preset, self._preset_default
            )
        else:
            self._attr_preset_mode = None
'''
if text.count(old) != 1:
    raise SystemExit(f'fan preset status anchor count={text.count(old)}')
fan.write_text(text.replace(old, new, 1))

catalog = Path('custom_components/localtuya/device_catalog.py')
text = catalog.read_text()
old = '''    if platform == "fan" and any(
        key in config
        for key in ("fan_speed_mapping", "fan_oscillating_mapping", "fan_preset_raw_type")
    ):
'''
new = '''    if platform == "fan" and any(
        key in config
        for key in (
            "fan_speed_mapping", "fan_oscillating_mapping", "fan_preset_raw_type",
            "fan_preset_default", "fan_no_switch",
        )
    ):
'''
if text.count(old) != 1:
    raise SystemExit(f'catalog fan validation anchor count={text.count(old)}')
text = text.replace(old, new, 1)
anchor = '''            config["fan_preset_values"] = normalized_values

'''
addition = anchor + '''        if "fan_preset_default" in config:
            default = config["fan_preset_default"]
            values = config.get("fan_preset_values")
            if not isinstance(default, str) or not isinstance(values, dict) or default not in values:
                return None
        if "fan_no_switch" in config:
            if config["fan_no_switch"] is not True or "fan_speed_control" not in config:
                return None
            if config.get("id") != config.get("fan_speed_control"):
                return None

'''
if text.count(anchor) != 1:
    raise SystemExit(f'catalog fan preset anchor count={text.count(anchor)}')
catalog.write_text(text.replace(anchor, addition, 1))

Path('tests/test_fan_residual_semantics.py').write_text('''"""Residual productless fan runtime semantics."""\n\nimport unittest\nfrom homeassistant.components.fan import FanEntityFeature\n\nfrom custom_components.localtuya.device_catalog import _validate_entity\nfrom custom_components.localtuya.fan import LocaltuyaFan\n\n\nclass DummyDevice:\n    async def set_dp(self, value, dp):\n        raise AssertionError("unexpected direct power write")\n\n    async def set_dps(self, values):\n        self.values = values\n\n\nclass FanResidualSemanticsTests(unittest.IsolatedAsyncioTestCase):\n    def test_catalog_accepts_bounded_no_switch_and_preset_default(self):\n        entity = {"platform": "fan", "config": {\n            "platform": "fan", "id": 3, "fan_speed_control": 3,\n            "fan_no_switch": True,\n            "fan_preset_dp": 3, "fan_preset_values": {"auto": "Auto", "manual": "4"},\n            "fan_preset_raw_type": "string", "fan_preset_default": "manual",\n        }}\n        self.assertIsNotNone(_validate_entity(entity))\n        bad = {"platform": "fan", "config": {**entity["config"], "fan_no_switch": False}}\n        self.assertIsNone(_validate_entity(bad))\n\n    def test_preset_unknown_raw_uses_declared_default(self):\n        obj = object.__new__(LocaltuyaFan)\n        obj._config = {"fan_preset_dp": 3}\n        obj._preset_raw_to_name = {"Auto": "auto", "4": "manual"}\n        obj._preset_default = "manual"\n        obj._no_switch = False\n        obj._state = True\n        obj._is_on = None\n        obj._attr_percentage = None\n        obj._attr_oscillating = None\n        obj._attr_current_direction = None\n        obj._attr_preset_mode = None\n        obj.dps_conf = lambda key: "7"\n        obj.has_config = lambda key: key == "fan_preset_dp"\n        # Avoid LocalTuyaEntity status machinery for this focused assertion.\n        raw_preset = obj.dps_conf("fan_preset_dp")\n        obj._attr_preset_mode = obj._preset_raw_to_name.get(raw_preset, obj._preset_default)\n        self.assertEqual(obj._attr_preset_mode, "manual")\n\n    async def test_no_switch_fan_has_no_power_features_or_write_requirement(self):\n        obj = object.__new__(LocaltuyaFan)\n        obj._no_switch = True\n        obj._dp_id = 3\n        obj._device = DummyDevice()\n        with self.assertRaises(NotImplementedError):\n            await obj.async_turn_off()\n\n\nif __name__ == "__main__":\n    unittest.main()\n''')
