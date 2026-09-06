from pathlib import Path


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual < count:
        raise SystemExit(f"{path}: expected at least {count} occurrence(s), found {actual}: {old[:80]!r}")
    text = text.replace(old, new, count)
    p.write_text(text, encoding="utf-8")


# advanced_mapping.py: preserve legacy single-primary mapping while adding a
# bounded per-DP mapping table for catalog-imported multi-DP platform entities.
p = Path("custom_components/localtuya/advanced_mapping.py")
text = p.read_text(encoding="utf-8")
text = text.replace(
    'CONF_ADVANCED_MAPPING = "advanced_mapping"\n_MAX_RULES = 64\n',
    'CONF_ADVANCED_MAPPING = "advanced_mapping"\nCONF_ADVANCED_MAPPING_BY_DP = "advanced_mapping_by_dp"\n_MAX_RULES = 64\n_MAX_MAPPING_DPS = 32\n',
    1,
)
marker = '\n\ndef advanced_mapping_dp_references(value: Any) -> set[int]:\n'
insert = '''\n\ndef validate_advanced_mapping_by_dp(value: Any) -> dict[str, list[dict[str, Any]]] | None:\n    """Validate a bounded DP -> declarative mapping table."""\n    if not isinstance(value, dict) or not value or len(value) > _MAX_MAPPING_DPS:\n        return None\n    result: dict[str, list[dict[str, Any]]] = {}\n    for raw_dp, raw_rules in value.items():\n        dp_id = _normalize_dp(raw_dp)\n        rules = validate_advanced_mapping(raw_rules)\n        key = str(dp_id) if dp_id is not None else None\n        if key is None or rules is None or key in result:\n            return None\n        result[key] = rules\n    return result\n\n\ndef advanced_mapping_by_dp_references(value: Any) -> set[int]:\n    """Return both mapped DPS and cross-DP references from a mapping table."""\n    mappings = validate_advanced_mapping_by_dp(value)\n    if mappings is None:\n        return set()\n    result = {int(dp_id) for dp_id in mappings}\n    for rules in mappings.values():\n        result.update(advanced_mapping_dp_references(rules))\n    return result\n\n\ndef prune_advanced_mapping_by_dp(\n    value: Any, optional_dps: set[int], available_dps: set[int]\n) -> dict[str, list[dict[str, Any]]] | None:\n    """Prune mappings whose mapped or referenced optional DPS are absent."""\n    mappings = validate_advanced_mapping_by_dp(value)\n    if mappings is None:\n        return None\n    result: dict[str, list[dict[str, Any]]] = {}\n    for raw_dp, rules in mappings.items():\n        dp_id = int(raw_dp)\n        if dp_id in optional_dps and dp_id not in available_dps:\n            continue\n        pruned = prune_advanced_mapping(rules, optional_dps, available_dps)\n        if pruned is not None:\n            result[raw_dp] = pruned\n    return result or None\n'''
if marker not in text:
    raise SystemExit("advanced_mapping.py insertion marker missing")
text = text.replace(marker, insert + marker, 1)
p.write_text(text, encoding="utf-8")

# common.py: request every referenced DP, select mappings by DP, follow mapped
# redirects recursively, and provide grouped mapped writes.
replace(
    "custom_components/localtuya/common.py",
    '''from .advanced_mapping import (\n    CONF_ADVANCED_MAPPING,\n    advanced_mapping_dp_references,\n    map_value_from_dps,\n    map_value_to_dps,\n    validate_advanced_mapping,\n)''',
    '''from .advanced_mapping import (\n    CONF_ADVANCED_MAPPING,\n    CONF_ADVANCED_MAPPING_BY_DP,\n    advanced_mapping_by_dp_references,\n    advanced_mapping_dp_references,\n    map_value_from_dps,\n    map_value_to_dps,\n    validate_advanced_mapping,\n    validate_advanced_mapping_by_dp,\n)''',
)
replace(
    "custom_components/localtuya/common.py",
    '''            for dp_id in advanced_mapping_dp_references(entity_config.get(CONF_ADVANCED_MAPPING)):\n                device.dps_to_request[dp_id] = None\n            entity = entity_class(device, dev_entry, entity_config[CONF_ID])''',
    '''            for dp_id in advanced_mapping_dp_references(entity_config.get(CONF_ADVANCED_MAPPING)):\n                device.dps_to_request[dp_id] = None\n            for dp_id in advanced_mapping_by_dp_references(entity_config.get(CONF_ADVANCED_MAPPING_BY_DP)):\n                device.dps_to_request[dp_id] = None\n            entity = entity_class(device, dev_entry, entity_config[CONF_ID])''',
)
replace(
    "custom_components/localtuya/common.py",
    '''            for dp_id in advanced_mapping_dp_references(entity.get(CONF_ADVANCED_MAPPING)):\n                self.dps_to_request[dp_id] = None''',
    '''            for dp_id in advanced_mapping_dp_references(entity.get(CONF_ADVANCED_MAPPING)):\n                self.dps_to_request[dp_id] = None\n            for dp_id in advanced_mapping_by_dp_references(entity.get(CONF_ADVANCED_MAPPING_BY_DP)):\n                self.dps_to_request[dp_id] = None''',
)
replace(
    "custom_components/localtuya/common.py",
    '''        self._advanced_mapping = validate_advanced_mapping(self._config.get(CONF_ADVANCED_MAPPING)) or []\n        self._default_value = self._config.get(CONF_DEFAULT_VALUE)''',
    '''        self._advanced_mapping = validate_advanced_mapping(self._config.get(CONF_ADVANCED_MAPPING)) or []\n        self._advanced_mapping_by_dp = (\n            validate_advanced_mapping_by_dp(self._config.get(CONF_ADVANCED_MAPPING_BY_DP)) or {}\n        )\n        self._default_value = self._config.get(CONF_DEFAULT_VALUE)''',
)
old = '''    def dps(self, dp_index):\n        """Return a DP value, applying the entity mapping to its primary DP."""\n        value = self.raw_dps(dp_index)\n        if value is None or not self._advanced_mapping or int(dp_index) != int(self._dp_id):\n            return value\n        mapped, redirect_dp = map_value_from_dps(value, self._advanced_mapping, self._status)\n        if redirect_dp is not None:\n            redirected = self.raw_dps(redirect_dp)\n            if redirected is not None:\n                return redirected\n        return mapped\n\n    def dps_conf(self, conf_item):\n        dp_index = self._config.get(conf_item)\n        if dp_index is None:\n            self.warning("Entity %s is requesting unset index for option %s", self.entity_id, conf_item)\n        return self.dps(dp_index)\n\n    async def set_mapped_dp(self, state, dp_index=None):\n        """Write an HA value using the entity's advanced multi-DP mapping."""\n        dp_index = self._dp_id if dp_index is None else dp_index\n        if not self._advanced_mapping or int(dp_index) != int(self._dp_id):\n            await self._device.set_dp(state, dp_index)\n            return\n        states = map_value_to_dps(state, self._advanced_mapping, self._status, int(self._dp_id))\n        if len(states) == 1:\n            target_dp, raw_value = next(iter(states.items()))\n            await self._device.set_dp(raw_value, target_dp)\n        else:\n            await self._device.set_dps(states)\n'''
new = '''    def _mapping_for_dp(self, dp_index):\n        """Return a validated mapping for one DP, preserving legacy primary rules."""\n        if dp_index is None or isinstance(dp_index, bool):\n            return []\n        try:\n            dp_id = int(dp_index)\n        except (TypeError, ValueError):\n            return []\n        by_dp = getattr(self, "_advanced_mapping_by_dp", {})\n        mapped = by_dp.get(str(dp_id)) if isinstance(by_dp, dict) else None\n        if mapped:\n            return mapped\n        legacy = getattr(self, "_advanced_mapping", [])\n        return legacy if dp_id == int(self._dp_id) else []\n\n    def has_advanced_mapping(self, dp_index=None):\n        """Return whether one logical DP has a declarative catalog mapping."""\n        dp_index = self._dp_id if dp_index is None else dp_index\n        return bool(self._mapping_for_dp(dp_index))\n\n    def _mapped_dps_value(self, dp_index, seen):\n        value = self.raw_dps(dp_index)\n        rules = self._mapping_for_dp(dp_index)\n        if value is None or not rules:\n            return value\n        dp_id = int(dp_index)\n        if dp_id in seen:\n            self.warning("Advanced mapping redirect cycle at DPS %s", dp_id)\n            return value\n        mapped, redirect_dp = map_value_from_dps(value, rules, self._status)\n        if redirect_dp is not None:\n            return self._mapped_dps_value(redirect_dp, seen | {dp_id})\n        return mapped\n\n    def dps(self, dp_index):\n        """Return a DP value after any declarative per-DP mapping."""\n        return self._mapped_dps_value(dp_index, set())\n\n    def dps_conf(self, conf_item):\n        dp_index = self._config.get(conf_item)\n        if dp_index is None:\n            self.warning("Entity %s is requesting unset index for option %s", self.entity_id, conf_item)\n        return self.dps(dp_index)\n\n    async def set_mapped_dp(self, state, dp_index=None):\n        """Write an HA value using the mapping attached to its logical DP."""\n        dp_index = self._dp_id if dp_index is None else dp_index\n        rules = self._mapping_for_dp(dp_index)\n        if not rules:\n            await self._device.set_dp(state, dp_index)\n            return\n        states = map_value_to_dps(state, rules, self._status, int(dp_index))\n        if len(states) == 1:\n            target_dp, raw_value = next(iter(states.items()))\n            await self._device.set_dp(raw_value, target_dp)\n        else:\n            await self._device.set_dps(states)\n\n    async def set_mapped_dps(self, states):\n        """Map several logical DPS and send one conflict-free grouped write."""\n        writes = {}\n        for raw_dp, state in states.items():\n            dp_id = int(raw_dp)\n            rules = self._mapping_for_dp(dp_id)\n            mapped = map_value_to_dps(state, rules, self._status, dp_id) if rules else {dp_id: state}\n            for target_dp, raw_value in mapped.items():\n                target_dp = int(target_dp)\n                if target_dp in writes and writes[target_dp] != raw_value:\n                    raise ValueError(f"Conflicting advanced mapping writes for DP {target_dp}")\n                writes[target_dp] = raw_value\n        if not writes:\n            return\n        if len(writes) == 1:\n            target_dp, raw_value = next(iter(writes.items()))\n            await self._device.set_dp(raw_value, target_dp)\n        else:\n            await self._device.set_dps(writes)\n'''
replace("custom_components/localtuya/common.py", old, new)

# device_catalog.py: validate/reference/prune the new per-DP table.
replace(
    "custom_components/localtuya/device_catalog.py",
    '''from .advanced_mapping import (\n    CONF_ADVANCED_MAPPING,\n    advanced_mapping_dp_references,\n    prune_advanced_mapping,\n    validate_advanced_mapping,\n)''',
    '''from .advanced_mapping import (\n    CONF_ADVANCED_MAPPING,\n    CONF_ADVANCED_MAPPING_BY_DP,\n    advanced_mapping_by_dp_references,\n    advanced_mapping_dp_references,\n    prune_advanced_mapping,\n    prune_advanced_mapping_by_dp,\n    validate_advanced_mapping,\n    validate_advanced_mapping_by_dp,\n)''',
)
replace(
    "custom_components/localtuya/device_catalog.py",
    '''    result.update(advanced_mapping_dp_references(config.get(CONF_ADVANCED_MAPPING)))\n    return result''',
    '''    result.update(advanced_mapping_dp_references(config.get(CONF_ADVANCED_MAPPING)))\n    result.update(advanced_mapping_by_dp_references(config.get(CONF_ADVANCED_MAPPING_BY_DP)))\n    return result''',
)
replace(
    "custom_components/localtuya/device_catalog.py",
    '''    if CONF_ADVANCED_MAPPING in config:\n        advanced = validate_advanced_mapping(config[CONF_ADVANCED_MAPPING])\n        if advanced is None:\n            return None\n        config[CONF_ADVANCED_MAPPING] = advanced\n    raw_overrides = entity.get("override_keys", [])''',
    '''    if CONF_ADVANCED_MAPPING in config:\n        advanced = validate_advanced_mapping(config[CONF_ADVANCED_MAPPING])\n        if advanced is None:\n            return None\n        config[CONF_ADVANCED_MAPPING] = advanced\n    if CONF_ADVANCED_MAPPING_BY_DP in config:\n        advanced_by_dp = validate_advanced_mapping_by_dp(config[CONF_ADVANCED_MAPPING_BY_DP])\n        if advanced_by_dp is None:\n            return None\n        config[CONF_ADVANCED_MAPPING_BY_DP] = advanced_by_dp\n    raw_overrides = entity.get("override_keys", [])''',
)
replace(
    "custom_components/localtuya/device_catalog.py",
    '''    if CONF_ADVANCED_MAPPING in config:\n        advanced = prune_advanced_mapping(config[CONF_ADVANCED_MAPPING], optional_dps, available_dps)\n        if advanced is None:\n            config.pop(CONF_ADVANCED_MAPPING, None)\n            removed.add(CONF_ADVANCED_MAPPING)\n        else:\n            config[CONF_ADVANCED_MAPPING] = advanced\n    for key, value in list(config.items()):''',
    '''    if CONF_ADVANCED_MAPPING in config:\n        advanced = prune_advanced_mapping(config[CONF_ADVANCED_MAPPING], optional_dps, available_dps)\n        if advanced is None:\n            config.pop(CONF_ADVANCED_MAPPING, None)\n            removed.add(CONF_ADVANCED_MAPPING)\n        else:\n            config[CONF_ADVANCED_MAPPING] = advanced\n    if CONF_ADVANCED_MAPPING_BY_DP in config:\n        advanced_by_dp = prune_advanced_mapping_by_dp(\n            config[CONF_ADVANCED_MAPPING_BY_DP], optional_dps, available_dps\n        )\n        if advanced_by_dp is None:\n            config.pop(CONF_ADVANCED_MAPPING_BY_DP, None)\n            removed.add(CONF_ADVANCED_MAPPING_BY_DP)\n        else:\n            config[CONF_ADVANCED_MAPPING_BY_DP] = advanced_by_dp\n    for key, value in list(config.items()):''',
)

# climate.py: use mapped writes only when the relevant DP has a Batch-F mapping.
p = Path("custom_components/localtuya/climate.py")
text = p.read_text(encoding="utf-8")
text = text.replace(
    '''        if states:\n            await self._device.set_dps(states)''',
    '''        if states:\n            if any(self.has_advanced_mapping(dp) for dp in states):\n                await self.set_mapped_dps(states)\n            else:\n                await self._device.set_dps(states)''',
    1,
)
text = text.replace(
    '''        raw = round(float(humidity) / self._target_humidity_precision)\n        await self._device.set_dp(raw, dp)''',
    '''        if self.has_advanced_mapping(dp):\n            await self.set_mapped_dp(humidity, dp)\n        else:\n            raw = round(float(humidity) / self._target_humidity_precision)\n            await self._device.set_dp(raw, dp)''',
    1,
)
# Generic enum writes: preserve existing raw value maps, but pass HA-facing identity
# values through advanced mappings when configured.
text = text.replace(
    '''        await self._device.set_dp(\n            self._conf_hvac_fan_mode_set[fan_mode],\n            self._conf_hvac_fan_mode_dp,\n        )''',
    '''        raw = self._conf_hvac_fan_mode_set[fan_mode]\n        if self.has_advanced_mapping(self._conf_hvac_fan_mode_dp):\n            await self.set_mapped_dp(raw, self._conf_hvac_fan_mode_dp)\n        else:\n            await self._device.set_dp(raw, self._conf_hvac_fan_mode_dp)''',
    1,
)
text = text.replace(
    '''                await self._device.set_dp(\n                    self._conf_hvac_mode_set[HVACMode.OFF], self._conf_hvac_mode_dp\n                )''',
    '''                raw = self._conf_hvac_mode_set[HVACMode.OFF]\n                if self.has_advanced_mapping(self._conf_hvac_mode_dp):\n                    await self.set_mapped_dp(raw, self._conf_hvac_mode_dp)\n                else:\n                    await self._device.set_dp(raw, self._conf_hvac_mode_dp)''',
    1,
)
text = text.replace(
    '''        await self._device.set_dp(\n            self._conf_hvac_mode_set[hvac_mode],\n            self._conf_hvac_mode_dp,\n        )''',
    '''        raw = self._conf_hvac_mode_set[hvac_mode]\n        if self.has_advanced_mapping(self._conf_hvac_mode_dp):\n            await self.set_mapped_dp(raw, self._conf_hvac_mode_dp)\n        else:\n            await self._device.set_dp(raw, self._conf_hvac_mode_dp)''',
    1,
)
for attr in ("_conf_hvac_swing_mode_dp", "_conf_hvac_swing_horizontal_mode_dp"):
    old = f'''        await self._device.set_dp(\n            self.{{"_conf_hvac_swing_mode_set" if attr == "_conf_hvac_swing_mode_dp" else "_conf_hvac_swing_horizontal_mode_set"}}[swing_mode],\n            self.{attr},\n        )'''
# Explicit replacements avoid generated-source ambiguity.
text = text.replace(
    '''        await self._device.set_dp(\n            self._conf_hvac_swing_mode_set[swing_mode],\n            self._conf_hvac_swing_mode_dp,\n        )''',
    '''        raw = self._conf_hvac_swing_mode_set[swing_mode]\n        if self.has_advanced_mapping(self._conf_hvac_swing_mode_dp):\n            await self.set_mapped_dp(raw, self._conf_hvac_swing_mode_dp)\n        else:\n            await self._device.set_dp(raw, self._conf_hvac_swing_mode_dp)''',
    1,
)
text = text.replace(
    '''        await self._device.set_dp(\n            self._conf_hvac_swing_horizontal_mode_set[swing_mode],\n            self._conf_hvac_swing_horizontal_mode_dp,\n        )''',
    '''        raw = self._conf_hvac_swing_horizontal_mode_set[swing_mode]\n        if self.has_advanced_mapping(self._conf_hvac_swing_horizontal_mode_dp):\n            await self.set_mapped_dp(raw, self._conf_hvac_swing_horizontal_mode_dp)\n        else:\n            await self._device.set_dp(raw, self._conf_hvac_swing_horizontal_mode_dp)''',
    1,
)
text = text.replace(
    '''            await self._device.set_dp(\n                self._conf_eco_value,\n                self._conf_eco_dp,\n            )''',
    '''            if self.has_advanced_mapping(self._conf_eco_dp):\n                await self.set_mapped_dp(self._conf_eco_value, self._conf_eco_dp)\n            else:\n                await self._device.set_dp(self._conf_eco_value, self._conf_eco_dp)''',
    1,
)
text = text.replace(
    '''        await self._device.set_dp(\n            self._conf_preset_set[preset_mode],\n            self._conf_preset_dp,\n        )''',
    '''        raw = self._conf_preset_set[preset_mode]\n        if self.has_advanced_mapping(self._conf_preset_dp):\n            await self.set_mapped_dp(raw, self._conf_preset_dp)\n        else:\n            await self._device.set_dp(raw, self._conf_preset_dp)''',
    1,
)
p.write_text(text, encoding="utf-8")

# Extend focused regression tests.
p = Path("tests/test_advanced_mapping.py")
text = p.read_text(encoding="utf-8")
text = text.replace(
    '''from custom_components.localtuya.advanced_mapping import (\n    advanced_mapping_dp_references,\n    map_value_from_dps,\n    map_value_to_dps,\n    prune_advanced_mapping,\n    validate_advanced_mapping,\n)''',
    '''from custom_components.localtuya.advanced_mapping import (\n    advanced_mapping_by_dp_references,\n    advanced_mapping_dp_references,\n    map_value_from_dps,\n    map_value_to_dps,\n    prune_advanced_mapping,\n    prune_advanced_mapping_by_dp,\n    validate_advanced_mapping,\n    validate_advanced_mapping_by_dp,\n)''',
    1,
)
needle = '''    def test_executable_or_unknown_keys_are_rejected(self):\n        self.assertIsNone(validate_advanced_mapping([{"template": "{{ evil }}"}]))\n        self.assertIsNone(validate_advanced_mapping([{"value_redirect_dp": "not-a-dp"}]))\n'''
addition = needle + '''\n    def test_per_dp_mapping_tracks_mapped_and_cross_dp_references(self):\n        mappings = validate_advanced_mapping_by_dp({\n            "1": [{\n                "dps_val": True,\n                "constraint_dp": 4,\n                "conditions": [\n                    {"dps_val": "manual", "value": "heat"},\n                    {"dps_val": "auto", "value": "auto"},\n                ],\n            }],\n            "16": [{"constraint_dp": 23, "conditions": [{"dps_val": "f", "value_redirect_dp": 17}]}],\n        })\n        self.assertIsNotNone(mappings)\n        self.assertEqual(advanced_mapping_by_dp_references(mappings), {1, 4, 16, 17, 23})\n\n    def test_per_dp_mapping_prunes_missing_optional_redirect(self):\n        mappings = {"16": [{"constraint_dp": 23, "conditions": [{"dps_val": "f", "value_redirect_dp": 17}]}]}\n        self.assertIsNone(prune_advanced_mapping_by_dp(mappings, {17}, {16, 23}))\n        self.assertIsNotNone(prune_advanced_mapping_by_dp(mappings, {17}, {16, 17, 23}))\n\n    def test_per_dp_mapping_rejects_invalid_dp_keys(self):\n        self.assertIsNone(validate_advanced_mapping_by_dp({"not-a-dp": [{"scale": 10}]}))\n'''
if needle not in text:
    raise SystemExit("test_advanced_mapping insertion marker missing")
text = text.replace(needle, addition, 1)
p.write_text(text, encoding="utf-8")

# Device-catalog regression ensures nested mapped DP keys count as declared refs.
p = Path("tests/test_device_catalog.py")
text = p.read_text(encoding="utf-8")
insert_marker = '\n\nif __name__ == "__main__":\n'
test_method = '''\n    def test_per_dp_advanced_mapping_requires_all_declared_dps(self):\n        payload = {\n            "schema_version": 3,\n            "mappings": [{\n                "id": "advanced-by-dp",\n                "match": {\n                    "product_ids": [],\n                    "required_dps": [1, 4],\n                    "optional_dps": [],\n                    "fingerprint": {"mode": "exact_dps"},\n                },\n                "confidence": "experimental",\n                "entities": [{\n                    "platform": "climate",\n                    "config": {\n                        "id": 1,\n                        "platform": "climate",\n                        "advanced_mapping_by_dp": {\n                            "1": [{"dps_val": True, "constraint_dp": 4, "conditions": [{"dps_val": "manual", "value": "heat"}]}]\n                        },\n                    },\n                }],\n            }],\n        }\n        self.assertEqual(len(validate_catalog(payload)["mappings"]), 1)\n        payload["mappings"][0]["match"]["required_dps"] = [1]\n        self.assertEqual(validate_catalog(payload)["mappings"], [])\n'''
if insert_marker not in text:
    raise SystemExit("test_device_catalog insertion marker missing")
text = text.replace(insert_marker, test_method + insert_marker, 1)
p.write_text(text, encoding="utf-8")

# Temporary staging files remove themselves from the resulting source tree.
Path("tools/_batch_f_runtime_patch.py").unlink(missing_ok=True)
Path(".github/workflows/batch-f-runtime-apply.yml").unlink(missing_ok=True)
