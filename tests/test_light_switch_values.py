"""Regression tests for exact Tuya light power mappings."""

from __future__ import annotations

import unittest

from custom_components.localtuya.light import LocaltuyaLight


class LightSwitchValueTests(unittest.TestCase):
    @staticmethod
    def _light(config=None):
        light = object.__new__(LocaltuyaLight)
        light._config = config or {}
        light._power_on_value = light._config.get("light_on_value", True)
        light._power_off_value = light._config.get("light_off_value", False)
        return light

    def test_default_bool_and_integer_reads_remain_compatible(self):
        light = self._light()
        self.assertIs(light._power_state_from_raw(True), True)
        self.assertIs(light._power_state_from_raw(False), False)
        self.assertIs(light._power_state_from_raw(1), True)
        self.assertIs(light._power_state_from_raw(0), False)

    def test_inverted_boolean_values_are_exact(self):
        light = self._light({"light_on_value": False, "light_off_value": True})
        self.assertIs(light._power_state_from_raw(False), True)
        self.assertIs(light._power_state_from_raw(True), False)

    def test_string_values_are_exact_and_case_sensitive(self):
        light = self._light({"light_on_value": "normal", "light_off_value": "slient"})
        self.assertIs(light._power_state_from_raw("normal"), True)
        self.assertIs(light._power_state_from_raw("slient"), False)
        self.assertIsNone(light._power_state_from_raw("Normal"))
        self.assertIsNone(light._power_state_from_raw(True))

    def test_null_read_fallback_does_not_change_write_values(self):
        light = self._light({"light_null_value": False})
        self.assertIs(light._power_state_from_raw(None), False)
        self.assertIs(light._power_on_value, True)
        self.assertIs(light._power_off_value, False)

    def test_custom_integer_mapping_is_type_strict(self):
        light = self._light({"light_on_value": 1, "light_off_value": 0})
        self.assertIs(light._power_state_from_raw(1), True)
        self.assertIs(light._power_state_from_raw(0), False)
        self.assertIsNone(light._power_state_from_raw(True))
        self.assertIsNone(light._power_state_from_raw(False))


if __name__ == "__main__":
    unittest.main()
