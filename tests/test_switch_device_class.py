"""Tests for Home Assistant switch device-class support."""

import unittest

import voluptuous as vol
from homeassistant.const import CONF_DEVICE_CLASS

from custom_components.localtuya.const import (
    CONF_PASSIVE_ENTITY,
    CONF_RESTORE_ON_RECONNECT,
)
from custom_components.localtuya.switch import flow_schema


class SwitchDeviceClassTests(unittest.TestCase):
    def test_outlet_device_class_is_accepted(self):
        schema = vol.Schema(flow_schema(["1"]))
        result = schema(
            {
                CONF_DEVICE_CLASS: "outlet",
                CONF_RESTORE_ON_RECONNECT: False,
                CONF_PASSIVE_ENTITY: False,
            }
        )
        self.assertEqual(result[CONF_DEVICE_CLASS], "outlet")

    def test_unknown_device_class_is_rejected(self):
        schema = vol.Schema(flow_schema(["1"]))
        with self.assertRaises(vol.Invalid):
            schema(
                {
                    CONF_DEVICE_CLASS: "not-a-real-switch-class",
                    CONF_RESTORE_ON_RECONNECT: False,
                    CONF_PASSIVE_ENTITY: False,
                }
            )


if __name__ == "__main__":
    unittest.main()
