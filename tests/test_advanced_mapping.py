"""Regression tests for catalog advanced mappings and multi-DP writes."""

import unittest

from custom_components.localtuya.advanced_mapping import (
    advanced_mapping_by_dp_references,
    advanced_mapping_dp_references,
    map_value_from_dps,
    map_value_to_dps,
    prune_advanced_mapping,
    prune_advanced_mapping_by_dp,
    validate_advanced_mapping,
    validate_advanced_mapping_by_dp,
)


class AdvancedMappingTests(unittest.TestCase):
    def test_exact_enum_mapping_round_trip(self):
        rules = validate_advanced_mapping([
            {"dps_val": "manual", "value": "heat"},
            {"dps_val": "auto", "value": "auto"},
        ])
        self.assertIsNotNone(rules)
        self.assertEqual(map_value_from_dps("manual", rules, {})[0], "heat")
        self.assertEqual(map_value_to_dps("auto", rules, {}, 2), {2: "auto"})

    def test_scale_invert_target_range_and_step(self):
        rules = validate_advanced_mapping([
            {
                "range": {"min": 0, "max": 1000},
                "target_range": {"min": 2700, "max": 6500},
                "invert": True,
                "step": 10,
            }
        ])
        self.assertIsNotNone(rules)
        value, _ = map_value_from_dps(0, rules, {})
        self.assertEqual(value, 6500)
        writes = map_value_to_dps(6500, rules, {}, 23)
        self.assertEqual(writes, {23: 0})

    def test_redirect_reads_secondary_dp(self):
        rules = validate_advanced_mapping([
            {"dps_val": "eco", "value_redirect_dp": 32},
        ])
        self.assertEqual(advanced_mapping_dp_references(rules), {32})
        value, redirect = map_value_from_dps("eco", rules, {"32": 18})
        self.assertEqual(value, "eco")
        self.assertEqual(redirect, 32)

    def test_conditional_mapping_sets_multiple_dps_atomically(self):
        rules = validate_advanced_mapping([
            {
                "dps_val": 1,
                "value": "comfort",
                "constraint_dp": 2,
                "conditions": [
                    {"dps_val": "manual", "value": "comfort"},
                    {"dps_val": "eco", "value": "eco"},
                ],
            }
        ])
        self.assertEqual(advanced_mapping_dp_references(rules), {2})
        self.assertEqual(
            map_value_to_dps("eco", rules, {"2": "manual"}, 16),
            {16: 1, 2: "eco"},
        )

    def test_invalid_active_condition_fails_closed(self):
        rules = validate_advanced_mapping([
            {
                "dps_val": 1,
                "value": 20,
                "constraint_dp": 2,
                "conditions": [{"dps_val": "locked", "invalid": True}],
            }
        ])
        with self.assertRaises(ValueError):
            map_value_to_dps(20, rules, {"2": "locked"}, 16)

    def test_optional_redirect_is_pruned_when_dp_absent(self):
        rules = [{"dps_val": "eco", "value_redirect_dp": 32}]
        self.assertIsNone(prune_advanced_mapping(rules, {32}, {1, 2}))
        self.assertIsNotNone(prune_advanced_mapping(rules, {32}, {1, 32}))

    def test_executable_or_unknown_keys_are_rejected(self):
        self.assertIsNone(validate_advanced_mapping([{"template": "{{ evil }}"}]))
        self.assertIsNone(validate_advanced_mapping([{"value_redirect_dp": "not-a-dp"}]))

    def test_per_dp_mapping_tracks_mapped_and_cross_dp_references(self):
        mappings = validate_advanced_mapping_by_dp({
            "1": [{
                "dps_val": True,
                "constraint_dp": 4,
                "conditions": [
                    {"dps_val": "manual", "value": "heat"},
                    {"dps_val": "auto", "value": "auto"},
                ],
            }],
            "16": [{"constraint_dp": 23, "conditions": [{"dps_val": "f", "value_redirect_dp": 17}]}],
        })
        self.assertIsNotNone(mappings)
        self.assertEqual(advanced_mapping_by_dp_references(mappings), {1, 4, 16, 17, 23})

    def test_per_dp_mapping_prunes_missing_optional_redirect(self):
        mappings = {"16": [{"constraint_dp": 23, "conditions": [{"dps_val": "f", "value_redirect_dp": 17}]}]}
        self.assertIsNotNone(prune_advanced_mapping_by_dp(mappings, {17}, {16, 23}))
        self.assertIsNotNone(prune_advanced_mapping_by_dp(mappings, {17}, {16, 17, 23}))

    def test_per_dp_mapping_rejects_invalid_dp_keys(self):
        self.assertIsNone(validate_advanced_mapping_by_dp({"not-a-dp": [{"scale": 10}]}))

    def test_ordered_bitmask_mapping_matches_tuya_local_semantics(self):
        rules = validate_advanced_mapping([
            {"dps_val": 0, "value": "ok", "bitmask": True},
            {"dps_val": 1, "value": "fault_a", "bitmask": True},
            {"dps_val": 2, "value": "fault_b", "bitmask": True},
            {"dps_val": 4, "value": "fault_c", "bitmask": True},
        ])
        self.assertIsNotNone(rules)
        self.assertEqual(map_value_from_dps(0, rules, {})[0], "ok")
        self.assertEqual(map_value_from_dps(1, rules, {})[0], "fault_a")
        self.assertEqual(map_value_from_dps(3, rules, {})[0], "fault_a")
        self.assertEqual(map_value_from_dps(6, rules, {})[0], "fault_b")
        self.assertEqual(map_value_from_dps(8, rules, {})[0], 8)

    def test_bitmask_mapping_rejects_non_integer_or_negative_masks(self):
        self.assertIsNone(validate_advanced_mapping([
            {"dps_val": "1", "value": "bad", "bitmask": True}
        ]))
        self.assertIsNone(validate_advanced_mapping([
            {"dps_val": -1, "value": "bad", "bitmask": True}
        ]))


if __name__ == "__main__":
    unittest.main()
