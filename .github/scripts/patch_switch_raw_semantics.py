from pathlib import Path

const = Path('custom_components/localtuya/const.py')
text = const.read_text()
anchor = '# switch\nCONF_CURRENT = "current"\n'
insert = '''# switch
CONF_SWITCH_ON_VALUE = "switch_on_value"
CONF_SWITCH_OFF_VALUE = "switch_off_value"
CONF_SWITCH_ICON_ON = "switch_icon_on"
CONF_SWITCH_ICON_OFF = "switch_icon_off"
CONF_SWITCH_MASK = "switch_mask"
CONF_SWITCH_MASK_ENDIANNESS = "switch_mask_endianness"
CONF_CURRENT = "current"
'''
if text.count(anchor) != 1:
    raise SystemExit(f'switch const anchor count={text.count(anchor)}')
const.write_text(text.replace(anchor, insert, 1))

switch = Path('custom_components/localtuya/switch.py')
text = switch.read_text()
old = '''from .const import (
    ATTR_CURRENT, ATTR_CURRENT_CONSUMPTION, ATTR_VOLTAGE, CONF_CURRENT,
    CONF_CURRENT_CONSUMPTION, CONF_DEFAULT_VALUE, CONF_PASSIVE_ENTITY,
    CONF_RESTORE_ON_RECONNECT, CONF_VOLTAGE,
)'''
new = '''from .const import (
    ATTR_CURRENT, ATTR_CURRENT_CONSUMPTION, ATTR_VOLTAGE, CONF_CURRENT,
    CONF_CURRENT_CONSUMPTION, CONF_DEFAULT_VALUE, CONF_PASSIVE_ENTITY,
    CONF_RESTORE_ON_RECONNECT, CONF_SWITCH_ICON_OFF, CONF_SWITCH_ICON_ON,
    CONF_SWITCH_MASK, CONF_SWITCH_MASK_ENDIANNESS, CONF_SWITCH_OFF_VALUE,
    CONF_SWITCH_ON_VALUE, CONF_VOLTAGE,
)'''
if text.count(old) != 1:
    raise SystemExit(f'switch import anchor count={text.count(old)}')
text = text.replace(old, new, 1)
old = '''        vol.Optional(CONF_DEVICE_CLASS): vol.In([device_class.value for device_class in SwitchDeviceClass]),
        vol.Required(CONF_RESTORE_ON_RECONNECT): bool,
'''
new = '''        vol.Optional(CONF_DEVICE_CLASS): vol.In([device_class.value for device_class in SwitchDeviceClass]),
        vol.Optional(CONF_SWITCH_ON_VALUE): vol.Any(str, int, bool),
        vol.Optional(CONF_SWITCH_OFF_VALUE): vol.Any(str, int, bool),
        vol.Optional(CONF_SWITCH_ICON_ON): str,
        vol.Optional(CONF_SWITCH_ICON_OFF): str,
        vol.Optional(CONF_SWITCH_MASK): str,
        vol.Optional(CONF_SWITCH_MASK_ENDIANNESS, default="big"): vol.In(("big", "little")),
        vol.Required(CONF_RESTORE_ON_RECONNECT): bool,
'''
if text.count(old) != 1:
    raise SystemExit(f'switch schema anchor count={text.count(old)}')
text = text.replace(old, new, 1)
old = '''        self._state = None
        device_class = self._config.get(CONF_DEVICE_CLASS)
'''
new = '''        self._state = None
        self._mapping_icon = None
        self._switch_on_value = self._config.get(CONF_SWITCH_ON_VALUE)
        self._switch_off_value = self._config.get(CONF_SWITCH_OFF_VALUE)
        mask_text = self._config.get(CONF_SWITCH_MASK)
        self._switch_mask_text = mask_text if isinstance(mask_text, str) else None
        self._switch_mask = int(mask_text, 16) if self._switch_mask_text else None
        self._switch_mask_endianness = self._config.get(CONF_SWITCH_MASK_ENDIANNESS, "big")
        device_class = self._config.get(CONF_DEVICE_CLASS)
'''
if text.count(old) != 1:
    raise SystemExit(f'switch init anchor count={text.count(old)}')
text = text.replace(old, new, 1)
old = '''    @property
    def is_on(self) -> bool | None:
        return self._state

    @property
    def extra_state_attributes(self):
'''
new = '''    @property
    def is_on(self) -> bool | None:
        return self._state

    @property
    def icon(self):
        return self._mapping_icon or super().icon

    def _masked_state(self, raw_state):
        if self._switch_mask is None or not isinstance(raw_state, str):
            return None
        try:
            value_text = raw_state if len(raw_state) % 2 == 0 else "0" + raw_state
            raw_bytes = bytes.fromhex(value_text)
            value = int.from_bytes(raw_bytes, self._switch_mask_endianness)
        except (ValueError, TypeError):
            return None
        scale = self._switch_mask & (1 + ~self._switch_mask)
        return bool((value & self._switch_mask) // scale)

    def _masked_write_value(self, enabled):
        raw_state = self.dps(self._dp_id)
        if not isinstance(raw_state, str) or self._switch_mask is None or not self._switch_mask_text:
            raise ValueError("Cannot mask unknown current switch value")
        try:
            value_text = raw_state if len(raw_state) % 2 == 0 else "0" + raw_state
            raw_bytes = bytes.fromhex(value_text)
            length = len(self._switch_mask_text) // 2
            current = int.from_bytes(raw_bytes, self._switch_mask_endianness)
            scale = self._switch_mask & (1 + ~self._switch_mask)
            result = (current & ~self._switch_mask) | (
                self._switch_mask & int(bool(enabled) * scale)
            )
            return result.to_bytes(length, self._switch_mask_endianness).hex()
        except (ValueError, OverflowError) as err:
            raise ValueError("Cannot mask invalid current switch value") from err

    @property
    def extra_state_attributes(self):
'''
if text.count(old) != 1:
    raise SystemExit(f'switch property anchor count={text.count(old)}')
text = text.replace(old, new, 1)
old = '''    def status_updated(self):
        raw_state = self.dps(self._dp_id)
        if isinstance(raw_state, bool):
            state = raw_state
        elif raw_state in (0, 1):
            state = bool(raw_state)
        else:
            state = None
        self._state = state
        if state is not None and not self._device.is_connecting:
            self._last_state = state

    async def async_turn_on(self, **kwargs):
        await self.set_mapped_dp(True)

    async def async_turn_off(self, **kwargs):
        await self.set_mapped_dp(False)
'''
new = '''    def status_updated(self):
        raw_state = self.dps(self._dp_id)
        if self._switch_mask is not None:
            state = self._masked_state(raw_state)
        elif CONF_SWITCH_ON_VALUE in self._config and CONF_SWITCH_OFF_VALUE in self._config:
            if raw_state == self._switch_on_value:
                state = True
            elif raw_state == self._switch_off_value:
                state = False
            else:
                state = None
        elif isinstance(raw_state, bool):
            state = raw_state
        elif raw_state in (0, 1):
            state = bool(raw_state)
        else:
            state = None
        self._state = state
        if state is True:
            self._mapping_icon = self._config.get(CONF_SWITCH_ICON_ON)
        elif state is False:
            self._mapping_icon = self._config.get(CONF_SWITCH_ICON_OFF)
        else:
            self._mapping_icon = None
        if state is not None and not self._device.is_connecting:
            self._last_state = state

    async def async_turn_on(self, **kwargs):
        if self._switch_mask is not None:
            await self._device.set_dp(self._masked_write_value(True), self._dp_id)
        elif CONF_SWITCH_ON_VALUE in self._config:
            await self._device.set_dp(self._switch_on_value, self._dp_id)
        else:
            await self.set_mapped_dp(True)

    async def async_turn_off(self, **kwargs):
        if self._switch_mask is not None:
            await self._device.set_dp(self._masked_write_value(False), self._dp_id)
        elif CONF_SWITCH_OFF_VALUE in self._config:
            await self._device.set_dp(self._switch_off_value, self._dp_id)
        else:
            await self.set_mapped_dp(False)
'''
if text.count(old) != 1:
    raise SystemExit(f'switch status anchor count={text.count(old)}')
switch.write_text(text.replace(old, new, 1))

catalog = Path('custom_components/localtuya/device_catalog.py')
text = catalog.read_text()
old = '''    CONF_MAPPED_EXTRA_STATE_ATTRIBUTE_MAPPINGS,
    CONF_SENSOR_UNIX_TIMESTAMP,
    PLATFORMS,
)'''
new = '''    CONF_MAPPED_EXTRA_STATE_ATTRIBUTE_MAPPINGS,
    CONF_SENSOR_UNIX_TIMESTAMP,
    CONF_SWITCH_ICON_OFF,
    CONF_SWITCH_ICON_ON,
    CONF_SWITCH_MASK,
    CONF_SWITCH_MASK_ENDIANNESS,
    CONF_SWITCH_OFF_VALUE,
    CONF_SWITCH_ON_VALUE,
    PLATFORMS,
)'''
if text.count(old) != 1:
    raise SystemExit(f'catalog switch import anchor count={text.count(old)}')
text = text.replace(old, new, 1)
anchor = '''    enabled_default = config.get("entity_registry_enabled_default")
'''
validation = '''    switch_mask = config.get(CONF_SWITCH_MASK)
    switch_special_keys = {
        CONF_SWITCH_ON_VALUE, CONF_SWITCH_OFF_VALUE, CONF_SWITCH_ICON_ON,
        CONF_SWITCH_ICON_OFF, CONF_SWITCH_MASK, CONF_SWITCH_MASK_ENDIANNESS,
    }
    if any(key in config for key in switch_special_keys):
        if platform != "switch":
            return None
        has_values = CONF_SWITCH_ON_VALUE in config or CONF_SWITCH_OFF_VALUE in config
        if has_values:
            if CONF_SWITCH_ON_VALUE not in config or CONF_SWITCH_OFF_VALUE not in config or switch_mask is not None:
                return None
            on_value, off_value = config[CONF_SWITCH_ON_VALUE], config[CONF_SWITCH_OFF_VALUE]
            if not isinstance(on_value, (str, int, bool)) or not isinstance(off_value, (str, int, bool)):
                return None
            if on_value == off_value and type(on_value) is type(off_value):
                return None
        if switch_mask is not None:
            if not isinstance(switch_mask, str) or not switch_mask or len(switch_mask) % 2 or len(switch_mask) > 32:
                return None
            try:
                mask_value = int(switch_mask, 16)
            except ValueError:
                return None
            if mask_value <= 0 or mask_value & (mask_value - 1):
                return None
            if config.get(CONF_SWITCH_MASK_ENDIANNESS, "big") not in {"big", "little"}:
                return None
        elif CONF_SWITCH_MASK_ENDIANNESS in config:
            return None
        for key in (CONF_SWITCH_ICON_ON, CONF_SWITCH_ICON_OFF):
            value = config.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                return None

'''
if text.count(anchor) != 1:
    raise SystemExit(f'catalog enabled anchor count={text.count(anchor)}')
catalog.write_text(text.replace(anchor, validation + anchor, 1))

Path('tests/test_switch_raw_semantics.py').write_text('''"""Exact non-boolean, inverted and masked Switch semantics."""\n\nimport unittest\n\nfrom custom_components.localtuya.device_catalog import _validate_entity\nfrom custom_components.localtuya.switch import LocaltuyaSwitch\n\n\nclass DummyDevice:\n    def __init__(self):\n        self.is_connecting = False\n        self.writes = []\n\n    async def set_dp(self, value, dp):\n        self.writes.append((dp, value))\n\n\nclass SwitchRawSemanticsTests(unittest.IsolatedAsyncioTestCase):\n    def make_switch(self, config, raw):\n        obj = object.__new__(LocaltuyaSwitch)\n        obj._dp_id = 1\n        obj._config = dict(config)\n        obj._state = None\n        obj._mapping_icon = None\n        obj._switch_on_value = config.get("switch_on_value")\n        obj._switch_off_value = config.get("switch_off_value")\n        obj._switch_mask_text = config.get("switch_mask")\n        obj._switch_mask = int(obj._switch_mask_text, 16) if obj._switch_mask_text else None\n        obj._switch_mask_endianness = config.get("switch_mask_endianness", "big")\n        obj._device = DummyDevice()\n        obj._last_state = None\n        obj.dps = lambda dp: raw[0]\n        return obj\n\n    async def test_string_raw_switch_reads_and_writes_exact_tokens(self):\n        raw = ["offline"]\n        obj = self.make_switch({"switch_on_value": "online", "switch_off_value": "offline"}, raw)\n        obj.status_updated()\n        self.assertIs(obj.is_on, False)\n        await obj.async_turn_on()\n        self.assertEqual(obj._device.writes[-1], (1, "online"))\n        raw[0] = "online"\n        obj.status_updated()\n        self.assertIs(obj.is_on, True)\n\n    async def test_inverted_boolean_and_dynamic_icons(self):\n        raw = [True]\n        obj = self.make_switch({\n            "switch_on_value": False, "switch_off_value": True,\n            "switch_icon_on": "mdi:bell", "switch_icon_off": "mdi:bell-off",\n        }, raw)\n        obj.status_updated()\n        self.assertIs(obj.is_on, False)\n        self.assertEqual(obj._mapping_icon, "mdi:bell-off")\n        await obj.async_turn_on()\n        self.assertEqual(obj._device.writes[-1], (1, False))\n\n    async def test_hex_mask_preserves_unrelated_bits(self):\n        raw = ["8011"]\n        obj = self.make_switch({"switch_mask": "0010", "switch_mask_endianness": "big"}, raw)\n        obj.status_updated()\n        self.assertIs(obj.is_on, True)\n        await obj.async_turn_off()\n        self.assertEqual(obj._device.writes[-1], (1, "8001"))\n        raw[0] = "8001"\n        await obj.async_turn_on()\n        self.assertEqual(obj._device.writes[-1], (1, "8011"))\n\n    def test_catalog_rejects_unsafe_switch_shapes(self):\n        good = {"platform": "switch", "config": {"platform": "switch", "id": 1, "switch_on_value": "online", "switch_off_value": "offline"}}\n        self.assertIsNotNone(_validate_entity(good))\n        self.assertIsNone(_validate_entity({"platform": "sensor", "config": {"platform": "sensor", "id": 1, "switch_on_value": True, "switch_off_value": False}}))\n        self.assertIsNone(_validate_entity({"platform": "switch", "config": {"platform": "switch", "id": 1, "switch_mask": "0030"}}))\n        self.assertIsNone(_validate_entity({"platform": "switch", "config": {"platform": "switch", "id": 1, "switch_mask_endianness": "little"}}))\n\n\nif __name__ == "__main__":\n    unittest.main()\n''')
