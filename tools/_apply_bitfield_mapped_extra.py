from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"anchor not found in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1) Runtime constant for attribute-scoped mappings.
const = Path("custom_components/localtuya/const.py")
replace_once(
    const,
    'CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS = "mapped_extra_state_attributes_dps"\n',
    'CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS = "mapped_extra_state_attributes_dps"\n'
    'CONF_MAPPED_EXTRA_STATE_ATTRIBUTE_MAPPINGS = "mapped_extra_state_attribute_mappings"\n',
)

# 2) Advanced mapping: bounded ordered bitfield matching.
adv = Path("custom_components/localtuya/advanced_mapping.py")
text = adv.read_text(encoding="utf-8")
text = text.replace(
    '_RULE_KEYS = {"dps_val", "value", "scale", "invert", "step", "range", "target_range", "constraint_dp", "conditions", "value_redirect_dp", "hidden", "invalid", "default"}',
    '_RULE_KEYS = {"dps_val", "value", "scale", "invert", "step", "range", "target_range", "constraint_dp", "conditions", "value_redirect_dp", "hidden", "invalid", "default", "bitmask"}',
    1,
)
text = text.replace(
    'for key in ("invert", "hidden", "invalid", "default"):\n',
    'for key in ("invert", "hidden", "invalid", "default", "bitmask"):\n',
    1,
)
anchor = '    for key in ("range", "target_range"):\n'
insert = '''    if result.get("bitmask"):\n        expected = result.get("dps_val")\n        if (\n            isinstance(expected, bool)\n            or not isinstance(expected, int)\n            or expected < 0\n        ):\n            return None\n'''
if insert not in text:
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit("advanced bitmask validation anchor missing")
    text = text[:idx] + insert + text[idx:]
helper = '''\n\ndef _rule_matches_raw(rule: dict[str, Any], actual: Any) -> bool:\n    """Match one ordered rule, including Tuya Local bitfield semantics."""\n    expected = rule.get("dps_val")\n    if rule.get("bitmask", False):\n        if expected == 0:\n            return str(actual) == str(expected)\n        try:\n            return (int(actual) & int(expected)) != 0\n        except (TypeError, ValueError):\n            return False\n    return _matches(expected, actual)\n'''
raw_anchor = '\n\ndef _find_rule_for_raw(rules: list[dict[str, Any]], raw: Any) -> dict[str, Any] | None:\n'
if helper not in text:
    idx = text.find(raw_anchor)
    if idx < 0:
        raise SystemExit("advanced raw matcher anchor missing")
    text = text[:idx] + helper + text[idx:]
text = text.replace(
    '        elif _matches(rule["dps_val"], raw):\n            return rule\n',
    '        elif _rule_matches_raw(rule, raw):\n            return rule\n',
    1,
)
adv.write_text(text, encoding="utf-8")

# 3) Common entity runtime: attribute-scoped mapped extras.
common = Path("custom_components/localtuya/common.py")
text = common.read_text(encoding="utf-8")
text = text.replace(
    '    CONF_EXTRA_STATE_ATTRIBUTES_DPS, CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS,\n',
    '    CONF_EXTRA_STATE_ATTRIBUTES_DPS, CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS,\n'
    '    CONF_MAPPED_EXTRA_STATE_ATTRIBUTE_MAPPINGS,\n',
    1,
)
getter_anchor = '''def get_mapped_extra_state_attribute_dps(config):\n    """Return validated catalog DPS attributes that must use declarative mapping."""\n    return _get_state_attribute_dps(config, CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS)\n'''
getter_new = getter_anchor + '''\n\ndef get_mapped_extra_state_attribute_mappings(config):\n    """Return validated attribute-name -> declarative mapping rules."""\n    configured = config.get(CONF_MAPPED_EXTRA_STATE_ATTRIBUTE_MAPPINGS)\n    if not isinstance(configured, dict) or not configured:\n        return {}\n    result = {}\n    for raw_name, raw_rules in configured.items():\n        if not isinstance(raw_name, str):\n            continue\n        name = raw_name.strip()\n        if not name or name in result:\n            continue\n        rules = validate_advanced_mapping(raw_rules)\n        if rules is None:\n            continue\n        result[name] = rules\n        if len(result) >= MAX_EXTRA_STATE_ATTRIBUTES:\n            break\n    return result\n'''
if 'def get_mapped_extra_state_attribute_mappings(config):' not in text:
    if getter_anchor not in text:
        raise SystemExit("common mapped getter anchor missing")
    text = text.replace(getter_anchor, getter_new, 1)
text = text.replace(
    '        self._mapped_extra_state_attribute_dps = get_mapped_extra_state_attribute_dps(self._config)\n',
    '        self._mapped_extra_state_attribute_dps = get_mapped_extra_state_attribute_dps(self._config)\n'
    '        self._mapped_extra_state_attribute_mappings = get_mapped_extra_state_attribute_mappings(self._config)\n',
    1,
)
old_extra = '''        for name, dp_id in getattr(self, "_mapped_extra_state_attribute_dps", {}).items():\n            dp_key = str(dp_id)\n            if dp_key in self._status:\n                attributes[name] = self.dps(dp_id)\n'''
new_extra = '''        for name, dp_id in getattr(self, "_mapped_extra_state_attribute_dps", {}).items():\n            dp_key = str(dp_id)\n            if dp_key in self._status:\n                rules = getattr(self, "_mapped_extra_state_attribute_mappings", {}).get(name)\n                if rules:\n                    attributes[name] = map_value_from_dps(\n                        self.raw_dps(dp_id), rules, self._status\n                    )[0]\n                else:\n                    attributes[name] = self.dps(dp_id)\n'''
if old_extra in text:
    text = text.replace(old_extra, new_extra, 1)
elif new_extra not in text:
    raise SystemExit("common extra attributes anchor missing")
setup_anchor = '''            for dp_id in get_mapped_extra_state_attribute_dps(entity_config).values():\n                device.dps_to_request[dp_id] = None\n'''
setup_new = setup_anchor + '''            for rules in get_mapped_extra_state_attribute_mappings(entity_config).values():\n                for dp_id in advanced_mapping_dp_references(rules):\n                    device.dps_to_request[dp_id] = None\n'''
if setup_new not in text:
    if setup_anchor not in text:
        raise SystemExit("common setup mapped extras anchor missing")
    text = text.replace(setup_anchor, setup_new, 1)
common.write_text(text, encoding="utf-8")

# 4) Remote catalog validation for both mapped DP refs and scoped rules.
catalog = Path("custom_components/localtuya/device_catalog.py")
text = catalog.read_text(encoding="utf-8")
text = text.replace(
    'from .const import CONF_EXTRA_STATE_ATTRIBUTES_DPS, PLATFORMS\n',
    'from .const import (\n'
    '    CONF_EXTRA_STATE_ATTRIBUTES_DPS,\n'
    '    CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS,\n'
    '    CONF_MAPPED_EXTRA_STATE_ATTRIBUTE_MAPPINGS,\n'
    '    PLATFORMS,\n'
    ')\n',
    1,
)
old_refs = '''    extra = config.get(CONF_EXTRA_STATE_ATTRIBUTES_DPS)\n    if isinstance(extra, dict):\n        for value in extra.values():\n            if isinstance(value, bool):\n                continue\n            try:\n                dp_id = int(value)\n            except (TypeError, ValueError):\n                continue\n            if 0 < dp_id <= MAX_DP_ID:\n                result.add(dp_id)\n'''
new_refs = '''    for extra_key in (\n        CONF_EXTRA_STATE_ATTRIBUTES_DPS,\n        CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS,\n    ):\n        extra = config.get(extra_key)\n        if isinstance(extra, dict):\n            for value in extra.values():\n                if isinstance(value, bool):\n                    continue\n                try:\n                    dp_id = int(value)\n                except (TypeError, ValueError):\n                    continue\n                if 0 < dp_id <= MAX_DP_ID:\n                    result.add(dp_id)\n    scoped = config.get(CONF_MAPPED_EXTRA_STATE_ATTRIBUTE_MAPPINGS)\n    if isinstance(scoped, dict):\n        for rules in scoped.values():\n            result.update(advanced_mapping_dp_references(rules))\n'''
if old_refs in text:
    text = text.replace(old_refs, new_refs, 1)
elif new_refs not in text:
    raise SystemExit("catalog refs anchor missing")
extra_validation_anchor = '''    if config.get("platform") is not None and config.get("platform") != platform:\n'''
extra_validation = '''    mapped_extra = config.get(CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS)\n    if mapped_extra is not None:\n        if not isinstance(mapped_extra, dict) or not mapped_extra or len(mapped_extra) > 32:\n            return None\n        normalized_mapped = {}\n        for raw_name, raw_dp in mapped_extra.items():\n            if not isinstance(raw_name, str):\n                return None\n            name = raw_name.strip()\n            if not name or name in {"state", "raw_state"} or name in normalized_mapped or isinstance(raw_dp, bool):\n                return None\n            try:\n                dp_id = int(raw_dp)\n            except (TypeError, ValueError):\n                return None\n            if dp_id <= 0 or dp_id > MAX_DP_ID:\n                return None\n            normalized_mapped[name] = dp_id\n        config[CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS] = normalized_mapped\n\n    scoped_mappings = config.get(CONF_MAPPED_EXTRA_STATE_ATTRIBUTE_MAPPINGS)\n    if scoped_mappings is not None:\n        if (\n            not isinstance(scoped_mappings, dict)\n            or not scoped_mappings\n            or len(scoped_mappings) > 32\n            or not isinstance(config.get(CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS), dict)\n        ):\n            return None\n        normalized_scoped = {}\n        for raw_name, raw_rules in scoped_mappings.items():\n            if not isinstance(raw_name, str):\n                return None\n            name = raw_name.strip()\n            if (\n                not name\n                or name in normalized_scoped\n                or name not in config[CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS]\n            ):\n                return None\n            rules = validate_advanced_mapping(raw_rules)\n            if rules is None:\n                return None\n            normalized_scoped[name] = rules\n        config[CONF_MAPPED_EXTRA_STATE_ATTRIBUTE_MAPPINGS] = normalized_scoped\n\n'''
if 'scoped_mappings = config.get(CONF_MAPPED_EXTRA_STATE_ATTRIBUTE_MAPPINGS)' not in text:
    idx = text.find(extra_validation_anchor)
    if idx < 0:
        raise SystemExit("catalog mapped validation anchor missing")
    text = text[:idx] + extra_validation + text[idx:]
catalog.write_text(text, encoding="utf-8")

# 5) Tests.
test_adv = Path("tests/test_advanced_mapping.py")
text = test_adv.read_text(encoding="utf-8")
method = '''\n    def test_ordered_bitmask_mapping_matches_tuya_local_semantics(self):\n        rules = validate_advanced_mapping([\n            {"dps_val": 0, "value": "ok", "bitmask": True},\n            {"dps_val": 1, "value": "fault_a", "bitmask": True},\n            {"dps_val": 2, "value": "fault_b", "bitmask": True},\n            {"dps_val": 4, "value": "fault_c", "bitmask": True},\n        ])\n        self.assertIsNotNone(rules)\n        self.assertEqual(map_value_from_dps(0, rules, {})[0], "ok")\n        self.assertEqual(map_value_from_dps(1, rules, {})[0], "fault_a")\n        self.assertEqual(map_value_from_dps(3, rules, {})[0], "fault_a")\n        self.assertEqual(map_value_from_dps(6, rules, {})[0], "fault_b")\n        self.assertEqual(map_value_from_dps(8, rules, {})[0], 8)\n\n    def test_bitmask_mapping_rejects_non_integer_or_negative_masks(self):\n        self.assertIsNone(validate_advanced_mapping([\n            {"dps_val": "1", "value": "bad", "bitmask": True}\n        ]))\n        self.assertIsNone(validate_advanced_mapping([\n            {"dps_val": -1, "value": "bad", "bitmask": True}\n        ]))\n'''
if 'test_ordered_bitmask_mapping_matches_tuya_local_semantics' not in text:
    marker = '\n\nif __name__ == "__main__":\n'
    idx = text.find(marker)
    if idx < 0:
        raise SystemExit("advanced tests anchor missing")
    text = text[:idx] + method + text[idx:]
test_adv.write_text(text, encoding="utf-8")

flags = Path("tests/test_catalog_runtime_flags.py")
text = flags.read_text(encoding="utf-8")
text = text.replace(
    '    get_non_persistent_dps,\n',
    '    LocalTuyaEntity,\n    get_mapped_extra_state_attribute_mappings,\n    get_non_persistent_dps,\n',
    1,
)
if 'from custom_components.localtuya.advanced_mapping import validate_advanced_mapping\n' not in text:
    text = text.replace(
        'from custom_components.localtuya.device_catalog import validate_catalog\n',
        'from custom_components.localtuya.device_catalog import validate_catalog\n'
        'from custom_components.localtuya.advanced_mapping import validate_advanced_mapping\n',
        1,
    )
extra_tests = '''\n\ndef test_attribute_scoped_mapping_does_not_transform_primary_dp():\n    rules = validate_advanced_mapping([\n        {"dps_val": 0, "value": "ok", "bitmask": True},\n        {"dps_val": 1, "value": "fault_a", "bitmask": True},\n        {"dps_val": 2, "value": "fault_b", "bitmask": True},\n    ])\n    entity = object.__new__(LocalTuyaEntity)\n    entity._status = {"19": 3}\n    entity._state = None\n    entity._last_state = None\n    entity._dp_id = 19\n    entity._config = {"friendly_name": "test"}\n    entity._extra_state_attribute_dps = {}\n    entity._mapped_extra_state_attribute_dps = {"description": 19}\n    entity._mapped_extra_state_attribute_mappings = {"description": rules}\n    entity._advanced_mapping = []\n    entity._advanced_mapping_by_dp = {}\n    entity.debug = lambda *args, **kwargs: None\n    entity.warning = lambda *args, **kwargs: None\n\n    assert entity.dps(19) == 3\n    assert entity.extra_state_attributes["description"] == "fault_a"\n\n\ndef test_catalog_accepts_scoped_mapped_extra_rules_and_tracks_dp():\n    payload = {\n        "schema_version": 3,\n        "mappings": [{\n            "id": "scoped-extra",\n            "match": {\n                "product_ids": [],\n                "fingerprint": {"mode": "exact_dps"},\n                "required_dps": [19],\n                "optional_dps": [],\n            },\n            "confidence": "experimental",\n            "entities": [{\n                "platform": "binary_sensor",\n                "config": {\n                    "id": 19,\n                    "platform": "binary_sensor",\n                    "mapped_extra_state_attributes_dps": {"description": 19},\n                    "mapped_extra_state_attribute_mappings": {\n                        "description": [\n                            {"dps_val": 0, "value": "ok", "bitmask": True},\n                            {"dps_val": 1, "value": "fault", "bitmask": True},\n                        ]\n                    },\n                },\n            }],\n        }],\n    }\n    result = validate_catalog(payload)\n    config = result["mappings"][0]["entities"][0]["config"]\n    assert config["mapped_extra_state_attributes_dps"] == {"description": 19}\n    assert config["mapped_extra_state_attribute_mappings"]["description"][1]["bitmask"] is True\n\n\ndef test_catalog_rejects_scoped_mapping_without_matching_attribute():\n    payload = {\n        "schema_version": 3,\n        "mappings": [{\n            "id": "bad-scoped-extra",\n            "match": {\n                "product_ids": [],\n                "fingerprint": {"mode": "exact_dps"},\n                "required_dps": [19],\n                "optional_dps": [],\n            },\n            "confidence": "experimental",\n            "entities": [{\n                "platform": "binary_sensor",\n                "config": {\n                    "id": 19,\n                    "platform": "binary_sensor",\n                    "mapped_extra_state_attributes_dps": {"description": 19},\n                    "mapped_extra_state_attribute_mappings": {\n                        "other": [{"dps_val": 1, "value": "fault", "bitmask": True}]\n                    },\n                },\n            }],\n        }],\n    }\n    assert validate_catalog(payload)["mappings"] == []\n'''
if 'test_attribute_scoped_mapping_does_not_transform_primary_dp' not in text:
    marker = '\n\ndef load_tests(loader, tests, pattern):\n'
    idx = text.find(marker)
    if idx < 0:
        raise SystemExit("runtime flags test anchor missing")
    text = text[:idx] + extra_tests + text[idx:]
flags.write_text(text, encoding="utf-8")

print("attribute-scoped bitfield runtime patch applied")
