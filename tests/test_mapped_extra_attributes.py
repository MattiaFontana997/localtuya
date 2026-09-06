"""Tests for catalog mapped extra-state attributes."""

import unittest

from homeassistant.const import CONF_FRIENDLY_NAME

from custom_components.localtuya.common import (
    LocalTuyaEntity,
    get_extra_state_attribute_dps,
    get_mapped_extra_state_attribute_dps,
)
from custom_components.localtuya.const import (
    CONF_EXTRA_STATE_ATTRIBUTES_DPS,
    CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS,
)


class MappedExtraAttributeTests(unittest.TestCase):
    def test_raw_and_mapped_extra_configs_are_independent(self):
        config = {
            CONF_EXTRA_STATE_ATTRIBUTES_DPS: {"raw": 20},
            CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS: {"unit": 23},
        }
        self.assertEqual(get_extra_state_attribute_dps(config), {"raw": 20})
        self.assertEqual(get_mapped_extra_state_attribute_dps(config), {"unit": 23})

    def test_mapped_extra_uses_dps_mapping_while_raw_remains_raw(self):
        entity = object.__new__(LocalTuyaEntity)
        entity._state = None
        entity._last_state = None
        entity._status = {"20": "raw-device-value", "23": "c"}
        entity._extra_state_attribute_dps = {"raw": 20}
        entity._mapped_extra_state_attribute_dps = {"unit": 23}
        entity._config = {CONF_FRIENDLY_NAME: "Test"}
        entity.dps = lambda dp_id: "celsius" if dp_id == 23 else None
        entity.debug = lambda *args, **kwargs: None
        attrs = LocalTuyaEntity.extra_state_attributes.fget(entity)
        self.assertEqual(attrs["raw"], "raw-device-value")
        self.assertEqual(attrs["unit"], "celsius")

    def test_invalid_mapped_extra_entries_are_ignored(self):
        config = {CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS: {
            "": 1, "bad": True, "zero": 0, "ok": "42"
        }}
        self.assertEqual(get_mapped_extra_state_attribute_dps(config), {"ok": 42})


if __name__ == "__main__":
    unittest.main()
