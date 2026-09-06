from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"missing patch anchor in {path}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "custom_components/localtuya/const.py",
    'CONF_EXTRA_STATE_ATTRIBUTES_DPS = "extra_state_attributes_dps"\n',
    'CONF_EXTRA_STATE_ATTRIBUTES_DPS = "extra_state_attributes_dps"\nCONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS = "mapped_extra_state_attributes_dps"\n',
)

replace_once(
    "custom_components/localtuya/common.py",
    "    CONF_EXTRA_STATE_ATTRIBUTES_DPS, CONF_LOCAL_KEY, CONF_MODEL,\n    CONF_PASSIVE_ENTITY, CONF_PROTOCOL_VERSION, CONF_RESET_DPIDS,",
    "    CONF_EXTRA_STATE_ATTRIBUTES_DPS, CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS,\n    CONF_LOCAL_KEY, CONF_MODEL, CONF_PASSIVE_ENTITY, CONF_PROTOCOL_VERSION, CONF_RESET_DPIDS,",
)

anchor = '''def get_extra_state_attribute_dps(config):\n    """Return validated catalog-provided raw DPS state attributes."""\n    configured = config.get(CONF_EXTRA_STATE_ATTRIBUTES_DPS)\n    if not isinstance(configured, dict):\n        return {}\n    result = {}\n    for raw_name, raw_dp in configured.items():\n        if not isinstance(raw_name, str):\n            continue\n        name = raw_name.strip()\n        if not name or name == ATTR_STATE or name in result or isinstance(raw_dp, bool):\n            continue\n        try:\n            dp_id = int(raw_dp)\n        except (TypeError, ValueError):\n            continue\n        if dp_id <= 0 or dp_id > 65535:\n            continue\n        result[name] = dp_id\n        if len(result) >= MAX_EXTRA_STATE_ATTRIBUTES:\n            break\n    return result\n\n\n'''
replacement = '''def _get_state_attribute_dps(config, key):\n    """Return validated catalog-provided DPS state attributes for one key."""\n    configured = config.get(key)\n    if not isinstance(configured, dict):\n        return {}\n    result = {}\n    for raw_name, raw_dp in configured.items():\n        if not isinstance(raw_name, str):\n            continue\n        name = raw_name.strip()\n        if not name or name == ATTR_STATE or name in result or isinstance(raw_dp, bool):\n            continue\n        try:\n            dp_id = int(raw_dp)\n        except (TypeError, ValueError):\n            continue\n        if dp_id <= 0 or dp_id > 65535:\n            continue\n        result[name] = dp_id\n        if len(result) >= MAX_EXTRA_STATE_ATTRIBUTES:\n            break\n    return result\n\n\ndef get_extra_state_attribute_dps(config):\n    """Return validated catalog-provided raw DPS state attributes."""\n    return _get_state_attribute_dps(config, CONF_EXTRA_STATE_ATTRIBUTES_DPS)\n\n\ndef get_mapped_extra_state_attribute_dps(config):\n    """Return validated catalog DPS attributes that must use declarative mapping."""\n    return _get_state_attribute_dps(config, CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS)\n\n\n'''
replace_once("custom_components/localtuya/common.py", anchor, replacement)

replace_once(
    "custom_components/localtuya/common.py",
    '''            for dp_id in get_extra_state_attribute_dps(entity_config).values():\n                device.dps_to_request[dp_id] = None\n            for dp_id in advanced_mapping_dp_references(entity_config.get(CONF_ADVANCED_MAPPING)):\n''',
    '''            for dp_id in get_extra_state_attribute_dps(entity_config).values():\n                device.dps_to_request[dp_id] = None\n            for dp_id in get_mapped_extra_state_attribute_dps(entity_config).values():\n                device.dps_to_request[dp_id] = None\n            for dp_id in advanced_mapping_dp_references(entity_config.get(CONF_ADVANCED_MAPPING)):\n''',
)

replace_once(
    "custom_components/localtuya/common.py",
    '''        self._extra_state_attribute_dps = get_extra_state_attribute_dps(self._config)\n        self._advanced_mapping = validate_advanced_mapping(self._config.get(CONF_ADVANCED_MAPPING)) or []\n''',
    '''        self._extra_state_attribute_dps = get_extra_state_attribute_dps(self._config)\n        self._mapped_extra_state_attribute_dps = get_mapped_extra_state_attribute_dps(self._config)\n        self._advanced_mapping = validate_advanced_mapping(self._config.get(CONF_ADVANCED_MAPPING)) or []\n''',
)

replace_once(
    "custom_components/localtuya/common.py",
    '''        for name, dp_id in self._extra_state_attribute_dps.items():\n            dp_key = str(dp_id)\n            if dp_key in self._status:\n                attributes[name] = self._status[dp_key]\n        self.debug("Entity %s - Additional attributes: %s", self.name, attributes)\n''',
    '''        for name, dp_id in self._extra_state_attribute_dps.items():\n            dp_key = str(dp_id)\n            if dp_key in self._status:\n                attributes[name] = self._status[dp_key]\n        for name, dp_id in self._mapped_extra_state_attribute_dps.items():\n            dp_key = str(dp_id)\n            if dp_key in self._status:\n                attributes[name] = self.dps(dp_id)\n        self.debug("Entity %s - Additional attributes: %s", self.name, attributes)\n''',
)

p = Path("tests/test_mapped_extra_attributes.py")
if not p.exists():
    p.write_text('''"""Tests for catalog mapped extra-state attributes."""\n\nimport unittest\n\nfrom homeassistant.const import CONF_FRIENDLY_NAME\n\nfrom custom_components.localtuya.common import (\n    LocalTuyaEntity,\n    get_extra_state_attribute_dps,\n    get_mapped_extra_state_attribute_dps,\n)\nfrom custom_components.localtuya.const import (\n    CONF_EXTRA_STATE_ATTRIBUTES_DPS,\n    CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS,\n)\n\n\nclass MappedExtraAttributeTests(unittest.TestCase):\n    def test_raw_and_mapped_extra_configs_are_independent(self):\n        config = {\n            CONF_EXTRA_STATE_ATTRIBUTES_DPS: {"raw": 20},\n            CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS: {"unit": 23},\n        }\n        self.assertEqual(get_extra_state_attribute_dps(config), {"raw": 20})\n        self.assertEqual(get_mapped_extra_state_attribute_dps(config), {"unit": 23})\n\n    def test_mapped_extra_uses_dps_mapping_while_raw_remains_raw(self):\n        entity = object.__new__(LocalTuyaEntity)\n        entity._state = None\n        entity._last_state = None\n        entity._status = {"20": "raw-device-value", "23": "c"}\n        entity._extra_state_attribute_dps = {"raw": 20}\n        entity._mapped_extra_state_attribute_dps = {"unit": 23}\n        entity._config = {CONF_FRIENDLY_NAME: "Test"}\n        entity.dps = lambda dp_id: "celsius" if dp_id == 23 else None\n        entity.debug = lambda *args, **kwargs: None\n        attrs = LocalTuyaEntity.extra_state_attributes.fget(entity)\n        self.assertEqual(attrs["raw"], "raw-device-value")\n        self.assertEqual(attrs["unit"], "celsius")\n\n    def test_invalid_mapped_extra_entries_are_ignored(self):\n        config = {CONF_MAPPED_EXTRA_STATE_ATTRIBUTES_DPS: {\n            "": 1, "bad": True, "zero": 0, "ok": "42"\n        }}\n        self.assertEqual(get_mapped_extra_state_attribute_dps(config), {"ok": 42})\n\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding="utf-8")
