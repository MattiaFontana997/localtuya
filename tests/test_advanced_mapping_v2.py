"""Batch M advanced mapping v2 runtime regressions."""

import unittest

from custom_components.localtuya.advanced_mapping import (
    effective_mapping_metadata,
    map_value_from_dps,
    map_value_to_dps,
)


class AdvancedMappingV2Tests(unittest.TestCase):
    def test_condition_range_and_step_are_active_metadata(self):
        rules = [{
            "constraint_dp": 19,
            "conditions": [{
                "dps_val": "f",
                "range": {"min": 410, "max": 950},
                "step": 10,
            }],
        }]
        self.assertEqual(
            effective_mapping_metadata(700, rules, {"19": "f"}),
            {"range": {"min": 410.0, "max": 950.0}, "step": 10.0},
        )
        self.assertEqual(effective_mapping_metadata(200, rules, {"19": "c"}), {})

    def test_active_range_rejects_out_of_range_write(self):
        rules = [{
            "constraint_dp": 19,
            "conditions": [{
                "dps_val": "f",
                "range": {"min": 410, "max": 950},
                "step": 10,
            }],
        }]
        self.assertEqual(map_value_to_dps(723, rules, {"19": "f"}, 2), {2: 720})
        with self.assertRaises(ValueError):
            map_value_to_dps(300, rules, {"19": "f"}, 2)

    def test_requested_condition_wins_during_reverse_mapping(self):
        rules = [{
            "dps_val": True,
            "constraint_dp": 4,
            "conditions": [
                {"dps_val": "cold", "value": "cool"},
                {"dps_val": "hot", "value": "heat"},
            ],
        }]
        self.assertEqual(
            map_value_to_dps("heat", rules, {"4": "cold"}, 1),
            {1: True, 4: "hot"},
        )

    def test_condition_scale_is_applied_on_read(self):
        rules = [{
            "constraint_dp": 111,
            "conditions": [
                {"dps_val": "0", "scale": 10},
                {"dps_val": "1", "value_redirect_dp": 106},
            ],
        }]
        self.assertEqual(map_value_from_dps(235, rules, {"111": "0"}), (23.5, None))
        self.assertEqual(map_value_from_dps(235, rules, {"111": "1"}), (235, 106))

    def test_transform_order_matches_tuya_local(self):
        rules = [{
            "range": {"min": 10, "max": 110},
            "target_range": {"min": 100, "max": 200},
            "invert": True,
            "scale": 2,
        }]
        self.assertEqual(map_value_from_dps(30, rules, {})[0], 90)
        self.assertEqual(map_value_to_dps(90, rules, {}, 7), {7: 30})

    def test_recursive_redirect_write_maps_target(self):
        mappings = {
            "2": [{"value_redirect_dp": 3}],
            "3": [{"scale": 10, "step": 5}],
        }
        self.assertEqual(map_value_to_dps(21.2, mappings["2"], {}, 2, mappings), {3: 210})

    def test_recursive_redirect_cycle_fails_closed(self):
        mappings = {
            "2": [{"value_redirect_dp": 3}],
            "3": [{"value_redirect_dp": 2}],
        }
        with self.assertRaises(ValueError):
            map_value_to_dps(20, mappings["2"], {}, 2, mappings)


if __name__ == "__main__":
    unittest.main()
