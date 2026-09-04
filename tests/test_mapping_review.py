"""Tests for existing-device mapping review."""

import unittest

from custom_components.localtuya.device_mapper import (
    EntityCandidate,
    MappingConfidence,
    MappingSource,
    MappingTrust,
)
from custom_components.localtuya.mapping_review import (
    MappingReviewKind,
    apply_existing_mapping_reviews,
    build_existing_mapping_reviews,
    default_existing_mapping_selection,
)


def candidate(
    platform,
    dp,
    config,
    *,
    confidence=MappingConfidence.HIGH,
):
    """Build mapping candidate."""
    return EntityCandidate(
        platform=platform,
        primary_dp=dp,
        confidence=confidence,
        config=config,
        matched_codes=(),
        referenced_dps=(dp,),
        source=MappingSource.CATALOG,
        trust=MappingTrust.VERIFIED,
    )


class MappingReviewTests(
    unittest.TestCase
):
    """Existing configuration comparison tests."""

    def test_update_preserves_local_fields_and_name(
        self,
    ):
        existing = [
            {
                "id": 1,
                "platform": "climate",
                "friendly_name":
                    "My Thermostat",
                "preset_set":
                    "auto/manual",
                "precision": 0.1,
                "my_custom_setting":
                    "keep-me",
            }
        ]

        candidates = [
            candidate(
                "climate",
                1,
                {
                    "id": 1,
                    "platform":
                        "climate",
                    "friendly_name":
                        "Remote Name",
                    "preset_set":
                        (
                            "auto/manual/"
                            "temporary/boost/"
                            "holiday"
                        ),
                    "precision": 0.1,
                    "hvac_mode_dp": 103,
                },
            )
        ]

        reviews = (
            build_existing_mapping_reviews(
                existing,
                candidates,
            )
        )

        self.assertEqual(
            len(reviews),
            1,
        )

        review = reviews[0]

        self.assertEqual(
            review.kind,
            MappingReviewKind.UPDATE,
        )

        self.assertEqual(
            review.changed_keys,
            (
                "hvac_mode_dp",
                "preset_set",
            ),
        )

        self.assertEqual(
            review.proposed_config[
                "friendly_name"
            ],
            "My Thermostat",
        )

        self.assertEqual(
            review.proposed_config[
                "my_custom_setting"
            ],
            "keep-me",
        )

        self.assertEqual(
            review.proposed_config[
                "preset_set"
            ],
            (
                "auto/manual/"
                "temporary/boost/"
                "holiday"
            ),
        )

    def test_identical_candidate_is_current(
        self,
    ):
        existing = [
            {
                "id": 1,
                "platform": "switch",
                "friendly_name":
                    "Kitchen",
                "restore_on_reconnect":
                    False,
            }
        ]

        candidates = [
            candidate(
                "switch",
                1,
                {
                    "id": 1,
                    "platform":
                        "switch",
                    "friendly_name":
                        "Different Name",
                    "restore_on_reconnect":
                        False,
                },
            )
        ]

        review = (
            build_existing_mapping_reviews(
                existing,
                candidates,
            )[0]
        )

        self.assertEqual(
            review.kind,
            MappingReviewKind.CURRENT,
        )

        self.assertEqual(
            review.changed_keys,
            (),
        )

    def test_same_dp_other_platform_is_conflict(
        self,
    ):
        existing = [
            {
                "id": 1,
                "platform": "switch",
                "friendly_name":
                    "Existing Switch",
            }
        ]

        candidates = [
            candidate(
                "climate",
                1,
                {
                    "id": 1,
                    "platform":
                        "climate",
                    "friendly_name":
                        "Climate",
                },
            )
        ]

        review = (
            build_existing_mapping_reviews(
                existing,
                candidates,
            )[0]
        )

        self.assertEqual(
            review.kind,
            MappingReviewKind.CONFLICT,
        )

        self.assertFalse(
            review.actionable
        )

    def test_new_candidate_on_unused_dp_is_new(
        self,
    ):
        existing = [
            {
                "id": 1,
                "platform": "switch",
                "friendly_name":
                    "Existing Switch",
            }
        ]

        candidates = [
            candidate(
                "number",
                32,
                {
                    "id": 32,
                    "platform":
                        "number",
                    "friendly_name":
                        "Holiday Temp",
                },
            )
        ]

        review = (
            build_existing_mapping_reviews(
                existing,
                candidates,
            )[0]
        )

        self.assertEqual(
            review.kind,
            MappingReviewKind.NEW,
        )

        self.assertTrue(
            review.actionable
        )


    def test_high_changes_are_selected_medium_are_not(
        self,
    ):
        existing = [
            {
                "id": 1,
                "platform": "switch",
                "friendly_name":
                    "Switch",
                "restore_on_reconnect":
                    True,
            }
        ]

        reviews = (
            build_existing_mapping_reviews(
                existing,
                [
                    candidate(
                        "switch",
                        1,
                        {
                            "id": 1,
                            "platform":
                                "switch",
                            "restore_on_reconnect":
                                False,
                        },
                    ),
                    candidate(
                        "number",
                        32,
                        {
                            "id": 32,
                            "platform":
                                "number",
                            "friendly_name":
                                "Holiday Temp",
                        },
                        confidence=(
                            MappingConfidence.MEDIUM
                        ),
                    ),
                ],
            )
        )

        defaults = (
            default_existing_mapping_selection(
                reviews
            )
        )

        self.assertEqual(
            defaults,
            ["switch:1"],
        )

    def test_apply_updates_without_deleting_or_overwriting_local_only_fields(
        self,
    ):
        existing = [
            {
                "id": 1,
                "platform": "climate",
                "friendly_name":
                    "Thermostat",
                "preset_set":
                    "auto/manual",
                "local_only":
                    "preserve",
            },
            {
                "id": 40,
                "platform": "switch",
                "friendly_name":
                    "Child Lock",
            },
        ]

        reviews = (
            build_existing_mapping_reviews(
                existing,
                [
                    candidate(
                        "climate",
                        1,
                        {
                            "id": 1,
                            "platform":
                                "climate",
                            "friendly_name":
                                "Remote",
                            "preset_set":
                                (
                                    "auto/manual/"
                                    "holiday"
                                ),
                        },
                    ),
                    candidate(
                        "number",
                        32,
                        {
                            "id": 32,
                            "platform":
                                "number",
                            "friendly_name":
                                "Holiday Temp",
                            "scaling": 0.1,
                        },
                    ),
                ],
            )
        )

        result = (
            apply_existing_mapping_reviews(
                existing,
                reviews,
                {
                    "climate:1",
                    "number:32",
                },
            )
        )

        self.assertEqual(
            len(result),
            3,
        )

        self.assertEqual(
            result[0][
                "friendly_name"
            ],
            "Thermostat",
        )

        self.assertEqual(
            result[0][
                "local_only"
            ],
            "preserve",
        )

        self.assertEqual(
            result[0][
                "preset_set"
            ],
            "auto/manual/holiday",
        )

        # Unmatched local entity remains untouched.
        self.assertEqual(
            result[1],
            existing[1],
        )

        self.assertEqual(
            result[2]["id"],
            32,
        )

        self.assertEqual(
            result[2][
                "platform"
            ],
            "number",
        )


if __name__ == "__main__":
    unittest.main()


class MappingReviewLabelTests(
    unittest.TestCase
):
    """UI labels for existing-device review."""

    def test_update_label_contains_status_and_changes(
        self,
    ):
        from custom_components.localtuya.config_flow import (
            _existing_mapping_review_label,
        )

        existing = [
            {
                "id": 1,
                "platform": "climate",
                "friendly_name":
                    "Thermostat",
                "preset_set":
                    "auto/manual",
            }
        ]

        reviews = (
            build_existing_mapping_reviews(
                existing,
                [
                    candidate(
                        "climate",
                        1,
                        {
                            "id": 1,
                            "platform":
                                "climate",
                            "preset_set":
                                (
                                    "auto/manual/"
                                    "holiday"
                                ),
                            "hvac_mode_dp":
                                103,
                        },
                    )
                ],
            )
        )

        label = (
            _existing_mapping_review_label(
                reviews[0],
                {
                    "mapping_status_verified":
                        "Verified",
                },
                {
                    "mapping_change_update":
                        "Update",
                    "mapping_change_new":
                        "New entity",
                },
            )
        )

        self.assertIn(
            "Verified",
            label,
        )

        self.assertIn(
            "Update",
            label,
        )

        self.assertIn(
            "hvac_mode_dp",
            label,
        )

        self.assertIn(
            "preset_set",
            label,
        )

    def test_new_entity_label(
        self,
    ):
        from custom_components.localtuya.config_flow import (
            _existing_mapping_review_label,
        )

        reviews = (
            build_existing_mapping_reviews(
                [],
                [
                    candidate(
                        "number",
                        32,
                        {
                            "id": 32,
                            "platform":
                                "number",
                            "friendly_name":
                                "Holiday Temp",
                        },
                    )
                ],
            )
        )

        label = (
            _existing_mapping_review_label(
                reviews[0],
                {
                    "mapping_status_verified":
                        "Verified",
                },
                {
                    "mapping_change_update":
                        "Update",
                    "mapping_change_new":
                        "New entity",
                },
            )
        )

        self.assertIn(
            "New entity",
            label,
        )

        self.assertIn(
            "DP 32",
            label,
        )
