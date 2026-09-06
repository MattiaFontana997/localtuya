"""Tests for catalog-provided raw DP extra state attributes."""

import unittest

from homeassistant.const import CONF_FRIENDLY_NAME

from custom_components.localtuya.common import (
    LocalTuyaEntity,
    get_extra_state_attribute_dps,
)
from custom_components.localtuya.const import CONF_EXTRA_STATE_ATTRIBUTES_DPS


class ExtraStateAttributeTests(unittest.TestCase):
    def test_config_parser_accepts_named_dp_map(self):
        config = {
            CONF_EXTRA_STATE_ATTRIBUTES_DPS: {
                "work_mode": 2,
                "aux": "3",
            }
        }
        self.assertEqual(
            get_extra_state_attribute_dps(config),
            {"work_mode": 2, "aux": 3},
        )

    def test_entity_exposes_current_raw_dp_values(self):
        entity = object.__new__(LocalTuyaEntity)
        entity._config = {
            CONF_FRIENDLY_NAME: "Desk lamp",
            CONF_EXTRA_STATE_ATTRIBUTES_DPS: {"work_mode": 2},
        }
        entity._extra_state_attribute_dps = {"work_mode": 2}
        entity._status = {"2": "white"}
        entity._state = None
        entity._last_state = None
        entity.debug = lambda *args, **kwargs: None

        self.assertEqual(
            entity.extra_state_attributes,
            {"work_mode": "white"},
        )

    def test_missing_extra_dp_is_not_exposed(self):
        entity = object.__new__(LocalTuyaEntity)
        entity._config = {CONF_FRIENDLY_NAME: "Desk lamp"}
        entity._extra_state_attribute_dps = {"work_mode": 2}
        entity._status = {}
        entity._state = None
        entity._last_state = None
        entity.debug = lambda *args, **kwargs: None

        self.assertEqual(entity.extra_state_attributes, {})


if __name__ == "__main__":
    unittest.main()
