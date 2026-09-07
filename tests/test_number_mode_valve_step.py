"""Regression tests for catalog number mode and valve write step."""

import unittest
from homeassistant.components.number import NumberMode
from custom_components.localtuya.number import _configured_number_mode
from custom_components.localtuya.valve import _position_to_raw

class NumberModeValveStepTests(unittest.TestCase):
    def test_number_mode_preserves_slider_and_box(self):
        self.assertEqual(_configured_number_mode("slider"), NumberMode.SLIDER)
        self.assertEqual(_configured_number_mode("box"), NumberMode.BOX)
        self.assertEqual(_configured_number_mode(None), NumberMode.AUTO)
        self.assertEqual(_configured_number_mode("invalid"), NumberMode.AUTO)

    def test_valve_step_matches_tuya_local_write_rounding(self):
        self.assertEqual(_position_to_raw(53, 0, 100, False, 5), 55)
        self.assertEqual(_position_to_raw(47, 0, 100, False, 5), 45)
        self.assertEqual(_position_to_raw(47, 0, 100, True, 5), 55)

    def test_valve_step_never_silently_clamps_out_of_range(self):
        with self.assertRaises(ValueError):
            _position_to_raw(100, 0, 98, False, 5)
