from custom_components.localtuya.common import (
    LocalTuyaEntity,
    get_mapped_extra_state_attribute_mappings,
    get_non_persistent_dps,
    prune_missing_non_persistent_dps,
)
from custom_components.localtuya.device_catalog import validate_catalog
from custom_components.localtuya.advanced_mapping import validate_advanced_mapping


def test_non_persistent_dps_are_bounded_and_normalized():
    assert get_non_persistent_dps({"non_persistent_dps": [3, "7", 3, True, 0, 70000]}) == {3, 7}


def test_missing_non_persistent_dps_are_removed_from_cache():
    cached = {"1": True, "3": 123, "7": "opening"}
    prune_missing_non_persistent_dps(cached, {"1": False, "7": "closing"}, {3, 7})
    assert cached == {"1": True, "7": "opening"}


def test_present_non_persistent_dp_remains_until_latest_value_is_merged():
    cached = {"3": 123}
    incoming = {"3": 456}
    prune_missing_non_persistent_dps(cached, incoming, {3})
    assert cached == {"3": 123}
    cached.update(incoming)
    assert cached == {"3": 456}


def test_catalog_accepts_disabled_default_and_non_persistent_dps():
    payload = {
        "schema_version": 3,
        "mappings": [{
            "id": "flags-test",
            "match": {
                "product_ids": [],
                "fingerprint": {"mode": "exact_dps"},
                "required_dps": [1],
                "optional_dps": [3],
            },
            "confidence": "experimental",
            "entities": [{
                "platform": "sensor",
                "config": {
                    "id": 1,
                    "platform": "sensor",
                    "entity_registry_enabled_default": False,
                    "non_persistent_dps": [3],
                },
            }],
        }],
    }
    result = validate_catalog(payload)
    config = result["mappings"][0]["entities"][0]["config"]
    assert config["entity_registry_enabled_default"] is False
    assert config["non_persistent_dps"] == [3]


def test_catalog_rejects_bad_disabled_default_type():
    payload = {
        "schema_version": 3,
        "mappings": [{
            "id": "bad-hidden",
            "match": {
                "product_ids": [],
                "fingerprint": {"mode": "exact_dps"},
                "required_dps": [1],
                "optional_dps": [],
            },
            "confidence": "experimental",
            "entities": [{
                "platform": "sensor",
                "config": {
                    "id": 1,
                    "platform": "sensor",
                    "entity_registry_enabled_default": "false",
                },
            }],
        }],
    }
    assert validate_catalog(payload)["mappings"] == []


def test_catalog_rejects_undeclared_non_persistent_dp_reference():
    payload = {
        "schema_version": 3,
        "mappings": [{
            "id": "bad-transient-ref",
            "match": {
                "product_ids": [],
                "fingerprint": {"mode": "exact_dps"},
                "required_dps": [1],
                "optional_dps": [],
            },
            "confidence": "experimental",
            "entities": [{
                "platform": "sensor",
                "config": {
                    "id": 1,
                    "platform": "sensor",
                    "non_persistent_dps": [3],
                },
            }],
        }],
    }
    assert validate_catalog(payload)["mappings"] == []


def test_attribute_scoped_mapping_does_not_transform_primary_dp():
    rules = validate_advanced_mapping([
        {"dps_val": 0, "value": "ok", "bitmask": True},
        {"dps_val": 1, "value": "fault_a", "bitmask": True},
        {"dps_val": 2, "value": "fault_b", "bitmask": True},
    ])
    entity = object.__new__(LocalTuyaEntity)
    entity._status = {"19": 3}
    entity._state = None
    entity._last_state = None
    entity._dp_id = 19
    entity._config = {"friendly_name": "test"}
    entity._extra_state_attribute_dps = {}
    entity._mapped_extra_state_attribute_dps = {"description": 19}
    entity._mapped_extra_state_attribute_mappings = {"description": rules}
    entity._advanced_mapping = []
    entity._advanced_mapping_by_dp = {}
    entity.debug = lambda *args, **kwargs: None
    entity.warning = lambda *args, **kwargs: None

    assert entity.dps(19) == 3
    assert entity.extra_state_attributes["description"] == "fault_a"


def test_catalog_accepts_scoped_mapped_extra_rules_and_tracks_dp():
    payload = {
        "schema_version": 3,
        "mappings": [{
            "id": "scoped-extra",
            "match": {
                "product_ids": [],
                "fingerprint": {"mode": "exact_dps"},
                "required_dps": [19],
                "optional_dps": [],
            },
            "confidence": "experimental",
            "entities": [{
                "platform": "binary_sensor",
                "config": {
                    "id": 19,
                    "platform": "binary_sensor",
                    "mapped_extra_state_attributes_dps": {"description": 19},
                    "mapped_extra_state_attribute_mappings": {
                        "description": [
                            {"dps_val": 0, "value": "ok", "bitmask": True},
                            {"dps_val": 1, "value": "fault", "bitmask": True},
                        ]
                    },
                },
            }],
        }],
    }
    result = validate_catalog(payload)
    config = result["mappings"][0]["entities"][0]["config"]
    assert config["mapped_extra_state_attributes_dps"] == {"description": 19}
    assert config["mapped_extra_state_attribute_mappings"]["description"][1]["bitmask"] is True


def test_catalog_rejects_scoped_mapping_without_matching_attribute():
    payload = {
        "schema_version": 3,
        "mappings": [{
            "id": "bad-scoped-extra",
            "match": {
                "product_ids": [],
                "fingerprint": {"mode": "exact_dps"},
                "required_dps": [19],
                "optional_dps": [],
            },
            "confidence": "experimental",
            "entities": [{
                "platform": "binary_sensor",
                "config": {
                    "id": 19,
                    "platform": "binary_sensor",
                    "mapped_extra_state_attributes_dps": {"description": 19},
                    "mapped_extra_state_attribute_mappings": {
                        "other": [{"dps_val": 1, "value": "fault", "bitmask": True}]
                    },
                },
            }],
        }],
    }
    assert validate_catalog(payload)["mappings"] == []


def load_tests(loader, tests, pattern):
    """Include function regressions in the project's unittest CI runner."""
    import unittest

    tests.addTests(unittest.FunctionTestCase(test) for name, test in globals().items()
                   if name.startswith("test_") and callable(test))
    return tests
