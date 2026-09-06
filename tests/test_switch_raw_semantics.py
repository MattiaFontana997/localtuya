"""Exact non-boolean, inverted and masked Switch semantics."""

import unittest

from custom_components.localtuya.device_catalog import _validate_entity
from custom_components.localtuya.switch import LocaltuyaSwitch


class DummyDevice:
    def __init__(self):
        self.is_connecting = False
        self.writes = []

    async def set_dp(self, value, dp):
        self.writes.append((dp, value))


class SwitchRawSemanticsTests(unittest.IsolatedAsyncioTestCase):
    def make_switch(self, config, raw):
        obj = object.__new__(LocaltuyaSwitch)
        obj._dp_id = 1
        obj._config = dict(config)
        obj._state = None
        obj._mapping_icon = None
        obj._switch_on_value = config.get("switch_on_value")
        obj._switch_off_value = config.get("switch_off_value")
        obj._switch_mask_text = config.get("switch_mask")
        obj._switch_mask = int(obj._switch_mask_text, 16) if obj._switch_mask_text else None
        obj._switch_mask_endianness = config.get("switch_mask_endianness", "big")
        obj._device = DummyDevice()
        obj._last_state = None
        obj.dps = lambda dp: raw[0]
        return obj

    async def test_string_raw_switch_reads_and_writes_exact_tokens(self):
        raw = ["offline"]
        obj = self.make_switch({"switch_on_value": "online", "switch_off_value": "offline"}, raw)
        obj.status_updated()
        self.assertIs(obj.is_on, False)
        await obj.async_turn_on()
        self.assertEqual(obj._device.writes[-1], (1, "online"))
        raw[0] = "online"
        obj.status_updated()
        self.assertIs(obj.is_on, True)

    async def test_inverted_boolean_and_dynamic_icons(self):
        raw = [True]
        obj = self.make_switch({
            "switch_on_value": False, "switch_off_value": True,
            "switch_icon_on": "mdi:bell", "switch_icon_off": "mdi:bell-off",
        }, raw)
        obj.status_updated()
        self.assertIs(obj.is_on, False)
        self.assertEqual(obj._mapping_icon, "mdi:bell-off")
        await obj.async_turn_on()
        self.assertEqual(obj._device.writes[-1], (1, False))

    async def test_hex_mask_preserves_unrelated_bits(self):
        raw = ["8011"]
        obj = self.make_switch({"switch_mask": "0010", "switch_mask_endianness": "big"}, raw)
        obj.status_updated()
        self.assertIs(obj.is_on, True)
        await obj.async_turn_off()
        self.assertEqual(obj._device.writes[-1], (1, "8001"))
        raw[0] = "8001"
        await obj.async_turn_on()
        self.assertEqual(obj._device.writes[-1], (1, "8011"))

    def test_catalog_rejects_unsafe_switch_shapes(self):
        good = {"platform": "switch", "config": {"platform": "switch", "id": 1, "switch_on_value": "online", "switch_off_value": "offline"}}
        self.assertIsNotNone(_validate_entity(good))
        self.assertIsNone(_validate_entity({"platform": "sensor", "config": {"platform": "sensor", "id": 1, "switch_on_value": True, "switch_off_value": False}}))
        self.assertIsNone(_validate_entity({"platform": "switch", "config": {"platform": "switch", "id": 1, "switch_mask": "0030"}}))
        self.assertIsNone(_validate_entity({"platform": "switch", "config": {"platform": "switch", "id": 1, "switch_mask_endianness": "little"}}))


if __name__ == "__main__":
    unittest.main()
