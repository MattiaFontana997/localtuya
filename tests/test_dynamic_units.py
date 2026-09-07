"""Regression tests for dynamic Sensor/Number units."""

import unittest
from homeassistant.const import UnitOfTemperature
from custom_components.localtuya.const import CONF_DYNAMIC_UNIT_DP
from custom_components.localtuya.sensor import LocaltuyaSensor
from custom_components.localtuya.number import LocaltuyaNumber
from custom_components.localtuya.common import tuya_unit_from_ascii


def _entity(cls, raw_unit):
    entity = object.__new__(cls)
    entity._config = {CONF_DYNAMIC_UNIT_DP: 13}
    entity._attr_native_unit_of_measurement = None
    entity.dps = lambda dp: raw_unit if dp == 13 else None
    return entity


class DynamicUnitTests(unittest.TestCase):
    def test_ascii_unit_aliases_match_tuya_local(self):
        self.assertEqual(tuya_unit_from_ascii("C"), UnitOfTemperature.CELSIUS)
        self.assertEqual(tuya_unit_from_ascii("F"), UnitOfTemperature.FAHRENHEIT)
        self.assertEqual(tuya_unit_from_ascii("ppm"), "ppm")

    def test_sensor_uses_live_unit_dp(self):
        sensor = _entity(LocaltuyaSensor, "F")
        self.assertEqual(sensor.native_unit_of_measurement, UnitOfTemperature.FAHRENHEIT)

    def test_number_uses_live_unit_dp(self):
        number = _entity(LocaltuyaNumber, "C")
        self.assertEqual(number.native_unit_of_measurement, UnitOfTemperature.CELSIUS)

    def test_static_unit_remains_when_no_dynamic_dp(self):
        sensor = object.__new__(LocaltuyaSensor)
        sensor._config = {}
        sensor._attr_native_unit_of_measurement = "%"
        self.assertEqual(sensor.native_unit_of_measurement, "%")
