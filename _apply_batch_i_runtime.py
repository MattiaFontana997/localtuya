from pathlib import Path

common = Path('custom_components/localtuya/common.py')
text = common.read_text(encoding='utf-8')

old = '''_LOGGER = logging.getLogger(__name__)\nMAX_EXTRA_STATE_ATTRIBUTES = 32\n\n\ndef get_extra_state_attribute_dps(config):'''
new = '''_LOGGER = logging.getLogger(__name__)\nMAX_EXTRA_STATE_ATTRIBUTES = 32\nMAX_NON_PERSISTENT_DPS = 32\nCONF_ENTITY_REGISTRY_ENABLED_DEFAULT = "entity_registry_enabled_default"\nCONF_NON_PERSISTENT_DPS = "non_persistent_dps"\n\n\ndef get_non_persistent_dps(config):\n    """Return validated catalog-provided DPS that must not remain cached."""\n    configured = config.get(CONF_NON_PERSISTENT_DPS)\n    if not isinstance(configured, list) or not configured:\n        return set()\n    result = set()\n    for raw_dp in configured:\n        if isinstance(raw_dp, bool):\n            continue\n        try:\n            dp_id = int(raw_dp)\n        except (TypeError, ValueError):\n            continue\n        if 0 < dp_id <= 65535:\n            result.add(dp_id)\n        if len(result) >= MAX_NON_PERSISTENT_DPS:\n            break\n    return result\n\n\ndef prune_missing_non_persistent_dps(cached_status, incoming_status, dp_ids):\n    """Drop transient DPS that were not present in the latest device update."""\n    if not isinstance(cached_status, dict) or not isinstance(incoming_status, dict):\n        return\n    incoming_keys = {str(key) for key in incoming_status}\n    for dp_id in dp_ids:\n        key = str(dp_id)\n        if key not in incoming_keys:\n            cached_status.pop(key, None)\n            cached_status.pop(dp_id, None)\n\n\ndef get_extra_state_attribute_dps(config):'''
if old not in text:
    raise SystemExit('common helper marker not found')
text = text.replace(old, new, 1)

old = '''        self._unsub_interval = None\n        self._entities = []\n        self._local_key = self._dev_config_entry[CONF_LOCAL_KEY]'''
new = '''        self._unsub_interval = None\n        self._entities = []\n        self._non_persistent_dps = set()\n        self._local_key = self._dev_config_entry[CONF_LOCAL_KEY]'''
if old not in text:
    raise SystemExit('device init marker not found')
text = text.replace(old, new, 1)

old = '''        for entity in self._dev_config_entry[CONF_ENTITIES]:\n            self.dps_to_request[entity[CONF_ID]] = None\n            for dp_id in advanced_mapping_dp_references(entity.get(CONF_ADVANCED_MAPPING)):'''
new = '''        for entity in self._dev_config_entry[CONF_ENTITIES]:\n            self.dps_to_request[entity[CONF_ID]] = None\n            self._non_persistent_dps.update(get_non_persistent_dps(entity))\n            for dp_id in advanced_mapping_dp_references(entity.get(CONF_ADVANCED_MAPPING)):'''
if old not in text:
    raise SystemExit('device entity loop marker not found')
text = text.replace(old, new, 1)

old = '''    @callback\n    def status_updated(self, status):\n        self._status.update(status)\n        self._dispatch_status()'''
new = '''    @callback\n    def status_updated(self, status):\n        prune_missing_non_persistent_dps(\n            self._status, status, self._non_persistent_dps\n        )\n        self._status.update(status)\n        self._dispatch_status()'''
if old not in text:
    raise SystemExit('status_updated marker not found')
text = text.replace(old, new, 1)

old = '''        self._config = get_entity_config(config_entry, dp_id)\n        self._dp_id = dp_id\n        self._status = {}'''
new = '''        self._config = get_entity_config(config_entry, dp_id)\n        enabled_default = self._config.get(CONF_ENTITY_REGISTRY_ENABLED_DEFAULT)\n        if isinstance(enabled_default, bool):\n            self._attr_entity_registry_enabled_default = enabled_default\n        self._dp_id = dp_id\n        self._status = {}'''
if old not in text:
    raise SystemExit('entity init marker not found')
text = text.replace(old, new, 1)
common.write_text(text, encoding='utf-8')

catalog = Path('custom_components/localtuya/device_catalog.py')
text = catalog.read_text(encoding='utf-8')

old = '''def _config_dp_references(config):\n    result = set()\n    extra = config.get(CONF_EXTRA_STATE_ATTRIBUTES_DPS)'''
new = '''def _config_dp_references(config):\n    result = set()\n    non_persistent = config.get("non_persistent_dps")\n    if isinstance(non_persistent, list):\n        for value in non_persistent:\n            if isinstance(value, bool):\n                continue\n            try:\n                dp_id = int(value)\n            except (TypeError, ValueError):\n                continue\n            if 0 < dp_id <= MAX_DP_ID:\n                result.add(dp_id)\n    extra = config.get(CONF_EXTRA_STATE_ATTRIBUTES_DPS)'''
if old not in text:
    raise SystemExit('catalog refs marker not found')
text = text.replace(old, new, 1)

old = '''    config = copy.deepcopy(config)\n    if CONF_ADVANCED_MAPPING in config:'''
new = '''    config = copy.deepcopy(config)\n    enabled_default = config.get("entity_registry_enabled_default")\n    if enabled_default is not None and not isinstance(enabled_default, bool):\n        return None\n    non_persistent = config.get("non_persistent_dps")\n    if non_persistent is not None:\n        normalized_non_persistent = _normalize_dps(non_persistent)\n        if (\n            normalized_non_persistent is None\n            or not normalized_non_persistent\n            or len(normalized_non_persistent) > 32\n        ):\n            return None\n        config["non_persistent_dps"] = normalized_non_persistent\n    if CONF_ADVANCED_MAPPING in config:'''
if old not in text:
    raise SystemExit('catalog entity validation marker not found')
text = text.replace(old, new, 1)
catalog.write_text(text, encoding='utf-8')
