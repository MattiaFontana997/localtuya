from custom_components.localtuya.common import (
    get_non_persistent_dps,
    prune_missing_non_persistent_dps,
)
from custom_components.localtuya.device_catalog import validate_catalog


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


def load_tests(loader, tests, pattern):
    """Include function regressions in the project's unittest CI runner."""
    import unittest

    tests.addTests(unittest.FunctionTestCase(test) for name, test in globals().items()
                   if name.startswith("test_") and callable(test))
    return tests
