from __future__ import annotations

import json
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"{label}: expected one marker, found {text.count(old)}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Centralized post-preparation zero-config decision.
# ---------------------------------------------------------------------------
p = Path("custom_components/localtuya/zero_config.py")
s = p.read_text(encoding="utf-8")
if "def evaluate_prepared_zero_config(" not in s:
    marker = "\ndef evaluate_zero_config(candidates: Iterable[Any]) -> ZeroConfigResult:\n"
    helper = '''\n\ndef evaluate_prepared_zero_config(
    device_data: dict[str, Any],
    review_candidates: Iterable[Any],
) -> ZeroConfigResult:
    """Decide whether an already prepared QR device may be silently persisted.

    ``async_prepare_qr_device`` has already put deterministic HIGH mappings in
    ``device_data['entities']`` and left MEDIUM mappings in
    ``review_candidates``. Both single and bulk QR onboarding use this one
    fail-closed decision point.
    """
    review_candidates = list(review_candidates or [])
    if review_candidates:
        return ZeroConfigResult(
            ZeroConfigDecision.REVIEW_REQUIRED,
            [],
            "mapping_review_required",
        )

    if not isinstance(device_data, dict):
        return ZeroConfigResult(
            ZeroConfigDecision.MANUAL_REQUIRED,
            [],
            "invalid_device_data",
        )
    entities = device_data.get("entities")
    if not isinstance(entities, list) or not entities:
        return ZeroConfigResult(
            ZeroConfigDecision.MANUAL_REQUIRED,
            [],
            "no_candidates",
        )

    normalized: list[dict[str, Any]] = []
    seen_primary: set[int] = set()
    for config in entities:
        if not isinstance(config, dict) or not config:
            return ZeroConfigResult(
                ZeroConfigDecision.REVIEW_REQUIRED,
                [],
                "invalid_candidate_config",
            )
        raw_primary = config.get("id")
        if isinstance(raw_primary, bool):
            return ZeroConfigResult(
                ZeroConfigDecision.REVIEW_REQUIRED,
                [],
                "invalid_primary_dp",
            )
        try:
            primary = int(raw_primary)
        except (TypeError, ValueError):
            return ZeroConfigResult(
                ZeroConfigDecision.REVIEW_REQUIRED,
                [],
                "invalid_primary_dp",
            )
        if primary <= 0 or primary in seen_primary:
            return ZeroConfigResult(
                ZeroConfigDecision.REVIEW_REQUIRED,
                [],
                "ambiguous_primary_dp",
            )
        seen_primary.add(primary)
        normalized.append(copy.deepcopy(config))

    return ZeroConfigResult(
        ZeroConfigDecision.AUTO_CONFIGURE,
        normalized,
        "prepared_high_confidence_entities",
    )
'''
    s = replace_once(s, marker, helper + marker, "prepared zero-config helper")
p.write_text(s, encoding="utf-8")


# ---------------------------------------------------------------------------
# QR onboarding: move bulk to OptionsFlow, make it reachable and fail-closed.
# ---------------------------------------------------------------------------
p = Path("custom_components/localtuya/qr_onboarding.py")
s = p.read_text(encoding="utf-8")

old_import = '''from .zero_config import (
    ZeroConfigDecision,
    evaluate_zero_config,
)
'''
new_import = '''from .zero_config import (
    ZeroConfigDecision,
    evaluate_prepared_zero_config,
)
'''
if old_import in s:
    s = replace_once(s, old_import, new_import, "zero-config import")
elif "evaluate_prepared_zero_config" not in s:
    raise SystemExit("zero-config import: unexpected state")

if "def _qr_is_locally_eligible(" not in s:
    marker = '''def _qr_needs_host_fallback(reason: str) -> bool:
'''
    helper = '''def _qr_is_locally_eligible(device: dict[str, Any]) -> bool:
    """Return whether Tuya supplied enough routing metadata for LAN validation."""
    if not isinstance(device, dict):
        return False
    node_id = str(device.get("node_id") or "").strip()
    if node_id:
        return bool(
            str(device.get("gateway_id") or "").strip()
            and str(device.get("gateway_local_key") or "").strip()
        )
    return bool(str(device.get(CONF_LOCAL_KEY) or "").strip())


'''
    s = replace_once(s, marker, helper + marker, "local eligibility helper")

# Remove the misplaced bulk block from QrConfigFlowMixin.
start_marker = "    def _bulk_eligible_devices(self):\n"
end_marker = "    async def async_step_qr_choose_device(self, user_input=None):\n"
if start_marker in s:
    start = s.index(start_marker)
    end = s.index(end_marker, start)
    s = s[:start] + s[end:]

# Initial QR device list uses the same direct/child routing requirements.
old = '''        eligible = {
            device_id: device
            for device_id, device in devices.items()
            if (
                (
                    not device.get("node_id")
                    and device.get(CONF_LOCAL_KEY)
                )
                or (
                    device.get("node_id")
                    and device.get("gateway_id")
                    and device.get("gateway_local_key")
                )
            )
        }
'''
new = '''        eligible = {
            device_id: device
            for device_id, device in devices.items()
            if _qr_is_locally_eligible(device)
        }
'''
if old in s:
    s = replace_once(s, old, new, "initial eligibility")

# Single initial QR path uses the centralized prepared decision.
old = '''            if self._qr_medium_candidates:
                return await self.async_step_qr_mapping_review()
            if not self._qr_device_data.get(CONF_ENTITIES):
                return self.async_abort(reason="qr_mapping_not_found")
            return await self._async_finish_initial_qr()
'''
new = '''            decision = evaluate_prepared_zero_config(
                self._qr_device_data,
                self._qr_medium_candidates,
            )
            if decision.decision is ZeroConfigDecision.REVIEW_REQUIRED:
                return await self.async_step_qr_mapping_review()
            if decision.decision is not ZeroConfigDecision.AUTO_CONFIGURE:
                return self.async_abort(reason="qr_mapping_not_found")
            self._qr_device_data[CONF_ENTITIES] = copy.deepcopy(decision.entities)
            return await self._async_finish_initial_qr()
'''
if old in s:
    s = replace_once(s, old, new, "initial prepared decision")

old = '''                    if self._qr_medium_candidates:
                        return await self.async_step_qr_mapping_review()
                    if not self._qr_device_data.get(CONF_ENTITIES):
                        return self.async_abort(reason="qr_mapping_not_found")
                    return await self._async_finish_initial_qr()
'''
new = '''                    decision = evaluate_prepared_zero_config(
                        self._qr_device_data,
                        self._qr_medium_candidates,
                    )
                    if decision.decision is ZeroConfigDecision.REVIEW_REQUIRED:
                        return await self.async_step_qr_mapping_review()
                    if decision.decision is not ZeroConfigDecision.AUTO_CONFIGURE:
                        return self.async_abort(reason="qr_mapping_not_found")
                    self._qr_device_data[CONF_ENTITIES] = copy.deepcopy(decision.entities)
                    return await self._async_finish_initial_qr()
'''
if old in s:
    s = replace_once(s, old, new, "initial host prepared decision")

# Install the real bulk path in OptionsFlow.
options_anchor = '''class QrOptionsFlowMixin:
    """Options-flow steps for future device sync without repeating QR login."""

'''
if "    async def async_step_qr_bulk_choose_devices" not in s:
    bulk = '''class QrOptionsFlowMixin:
    """Options-flow steps for future device sync without repeating QR login."""

    async def _async_load_linked_qr_devices(self):
        """Refresh linked devices once and persist any refreshed QR token."""
        if getattr(self, "_qr_devices", None) and getattr(self, "_qr_cloud", None):
            return None
        auth = self.config_entry.data.get(CONF_QR_AUTH)
        if not isinstance(auth, dict) or not auth:
            return "qr_not_linked"
        self._qr_cloud = QrCloudClient(self.hass, auth)
        try:
            self._qr_devices = await self._qr_cloud.async_get_devices()
        except QrProvisioningError as exc:
            return exc.reason
        self._persist_qr_auth(self._qr_cloud.auth)
        return None

    def _bulk_eligible_devices(self):
        """Return linked devices not already configured in this entry."""
        devices = getattr(self, "_qr_devices", {})
        configured = set(self.config_entry.data.get(CONF_DEVICES, {}))
        return {
            str(device_id): device
            for device_id, device in devices.items()
            if str(device_id) not in configured
        }

    async def _async_bulk_prepare_devices(self, device_ids):
        """Provision selected devices sequentially while isolating failures."""
        devices = getattr(self, "_qr_devices", {})
        cloud = getattr(self, "_qr_cloud", None)
        successes = []
        failures = []
        for raw_device_id in device_ids:
            device_id = str(raw_device_id)
            cloud_device = devices.get(device_id)
            if not isinstance(cloud_device, dict):
                failures.append({"device_id": device_id, "reason": "device_not_found"})
                continue
            try:
                device_data, candidates = await async_prepare_qr_device(
                    self.hass,
                    cloud,
                    cloud_device,
                )
            except QrProvisioningError as exc:
                failures.append({"device_id": device_id, "reason": exc.reason})
                continue
            except Exception as exc:  # noqa: BLE001 - isolate one device in bulk mode.
                _LOGGER.debug(
                    "Bulk QR provisioning failed for one device: %s",
                    type(exc).__name__,
                )
                failures.append({"device_id": device_id, "reason": "probe_error"})
                continue
            successes.append(
                {
                    "device_id": device_id,
                    "device_data": device_data,
                    "candidates": candidates,
                }
            )
        return {"successes": successes, "failures": failures}

    @staticmethod
    def _qr_bulk_schema(eligible):
        """Build the privacy-safe multi-select schema for linked devices."""
        options = [
            {
                "value": str(device_id),
                "label": str(device.get(CONF_NAME) or device_id),
            }
            for device_id, device in eligible.items()
        ]
        return vol.Schema(
            {
                vol.Required(CONF_QR_BULK_DEVICE_IDS): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

    async def async_step_qr_bulk_choose_devices(self, user_input=None):
        """Select multiple linked Tuya devices for sequential LAN onboarding."""
        load_error = await self._async_load_linked_qr_devices()
        if load_error:
            return self.async_abort(reason=load_error)
        eligible = self._bulk_eligible_devices()
        if not eligible:
            return self.async_abort(reason="qr_no_new_local_devices")
        if user_input is not None:
            selected = [
                str(device_id)
                for device_id in user_input.get(CONF_QR_BULK_DEVICE_IDS, [])
                if str(device_id) in eligible
            ]
            if not selected:
                return self.async_show_form(
                    step_id="qr_bulk_choose_devices",
                    data_schema=self._qr_bulk_schema(eligible),
                    errors={"base": "select_at_least_one_device"},
                )
            self._qr_bulk_result = await self._async_bulk_prepare_devices(selected)
            self._qr_bulk_summary = None
            return await self.async_step_qr_bulk_summary()
        return self.async_show_form(
            step_id="qr_bulk_choose_devices",
            data_schema=self._qr_bulk_schema(eligible),
        )

    async def async_step_qr_bulk_summary(self, user_input=None):
        """Persist deterministic devices only and show a count-only summary."""
        if getattr(self, "_qr_bulk_summary", None) is None:
            result = getattr(
                self,
                "_qr_bulk_result",
                {"successes": [], "failures": []},
            )
            successes = result.get("successes", [])
            failures = result.get("failures", [])
            entry_data = copy.deepcopy(dict(self.config_entry.data))
            devices = entry_data.setdefault(CONF_DEVICES, {})
            if not isinstance(devices, dict):
                devices = {}
                entry_data[CONF_DEVICES] = devices

            added = []
            review_required = []
            for item in successes:
                device_data = copy.deepcopy(item["device_data"])
                decision = evaluate_prepared_zero_config(
                    device_data,
                    item.get("candidates", []),
                )
                if decision.decision is not ZeroConfigDecision.AUTO_CONFIGURE:
                    review_required.append(str(item["device_id"]))
                    continue
                device_data[CONF_ENTITIES] = copy.deepcopy(decision.entities)
                devices[str(item["device_id"])] = device_data
                added.append(str(item["device_id"]))

            if added and hasattr(self.hass, "config_entries"):
                entry_data[ATTR_UPDATED_AT] = str(int(time.time() * 1000))
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=entry_data,
                )

            self._qr_bulk_summary = {
                "added": added,
                "review_required": review_required,
                "failures": failures,
            }

        summary = self._qr_bulk_summary
        if user_input is not None:
            return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="qr_bulk_summary",
            data_schema=vol.Schema({}),
            description_placeholders={
                "added_count": str(len(summary["added"])),
                "failed_count": str(len(summary["failures"])),
                "review_count": str(len(summary["review_required"])),
            },
        )

'''
    s = replace_once(s, options_anchor, bulk, "OptionsFlow bulk insertion")

old = '''            menu_options=[
                "qr_add_device",
                "manual_add_device",
                "qr_relink",
                "qr_disconnect",
            ],
'''
new = '''            menu_options=[
                "qr_add_device",
                "qr_bulk_choose_devices",
                "manual_add_device",
                "qr_relink",
                "qr_disconnect",
            ],
'''
if old in s:
    s = replace_once(s, old, new, "bulk menu")

old = '''        eligible = {
            device_id: device
            for device_id, device in self._qr_devices.items()
            if device_id not in configured
            and device.get(CONF_LOCAL_KEY)
            and not device.get("node_id")
            and device.get("support_local", True)
        }
'''
new = '''        eligible = {
            device_id: device
            for device_id, device in self._qr_devices.items()
            if device_id not in configured
            and _qr_is_locally_eligible(device)
        }
'''
if old in s:
    s = replace_once(s, old, new, "linked single eligibility")

old = '''            if self._qr_medium_candidates:
                return await self.async_step_qr_add_mapping_review()
            if not self._qr_device_data.get(CONF_ENTITIES):
                return self.async_abort(reason="qr_mapping_not_found")
            return self._finish_qr_added_device()
'''
new = '''            decision = evaluate_prepared_zero_config(
                self._qr_device_data,
                self._qr_medium_candidates,
            )
            if decision.decision is ZeroConfigDecision.REVIEW_REQUIRED:
                return await self.async_step_qr_add_mapping_review()
            if decision.decision is not ZeroConfigDecision.AUTO_CONFIGURE:
                return self.async_abort(reason="qr_mapping_not_found")
            self._qr_device_data[CONF_ENTITIES] = copy.deepcopy(decision.entities)
            return self._finish_qr_added_device()
'''
if old in s:
    s = replace_once(s, old, new, "linked prepared decision")

old = '''                    if self._qr_medium_candidates:
                        return await self.async_step_qr_add_mapping_review()
                    if not self._qr_device_data.get(CONF_ENTITIES):
                        return self.async_abort(reason="qr_mapping_not_found")
                    return self._finish_qr_added_device()
'''
new = '''                    decision = evaluate_prepared_zero_config(
                        self._qr_device_data,
                        self._qr_medium_candidates,
                    )
                    if decision.decision is ZeroConfigDecision.REVIEW_REQUIRED:
                        return await self.async_step_qr_add_mapping_review()
                    if decision.decision is not ZeroConfigDecision.AUTO_CONFIGURE:
                        return self.async_abort(reason="qr_mapping_not_found")
                    self._qr_device_data[CONF_ENTITIES] = copy.deepcopy(decision.entities)
                    return self._finish_qr_added_device()
'''
if old in s:
    s = replace_once(s, old, new, "linked host prepared decision")

p.write_text(s, encoding="utf-8")


# ---------------------------------------------------------------------------
# Translations: keep every supported language at exact key parity.
# ---------------------------------------------------------------------------
translations = {
    "en": (
        "Add multiple devices from linked account",
        "Select several linked Tuya devices and validate them sequentially over LAN.",
        "Add multiple devices",
        "Select one or more Tuya devices. LocalTuya validates each device sequentially; devices needing mapping review are never saved automatically.",
        "Tuya devices",
        "Bulk onboarding summary",
        "Added automatically: {added_count}. Needs mapping review: {review_count}. Failed validation: {failed_count}. Devices needing review were not saved automatically.",
        "Select at least one device.",
    ),
    "it": (
        "Aggiungi più dispositivi dall'account collegato",
        "Seleziona più dispositivi Tuya collegati e validali in sequenza sulla LAN.",
        "Aggiungi più dispositivi",
        "Seleziona uno o più dispositivi Tuya. LocalTuya li valida in sequenza; quelli che richiedono revisione del mapping non vengono mai salvati automaticamente.",
        "Dispositivi Tuya",
        "Riepilogo aggiunta multipla",
        "Aggiunti automaticamente: {added_count}. Da revisionare: {review_count}. Validazione fallita: {failed_count}. I dispositivi da revisionare non sono stati salvati automaticamente.",
        "Seleziona almeno un dispositivo.",
    ),
    "de": (
        "Mehrere Geräte aus dem verknüpften Konto hinzufügen",
        "Mehrere verknüpfte Tuya-Geräte auswählen und nacheinander im LAN prüfen.",
        "Mehrere Geräte hinzufügen",
        "Wähle ein oder mehrere Tuya-Geräte. LocalTuya prüft sie nacheinander; Geräte mit erforderlicher Zuordnungsprüfung werden nicht automatisch gespeichert.",
        "Tuya-Geräte",
        "Zusammenfassung der Mehrfach-Einrichtung",
        "Automatisch hinzugefügt: {added_count}. Zuordnung prüfen: {review_count}. Prüfung fehlgeschlagen: {failed_count}. Geräte mit Prüfbedarf wurden nicht automatisch gespeichert.",
        "Wähle mindestens ein Gerät aus.",
    ),
    "pt-BR": (
        "Adicionar vários dispositivos da conta vinculada",
        "Selecione vários dispositivos Tuya vinculados e valide-os em sequência pela LAN.",
        "Adicionar vários dispositivos",
        "Selecione um ou mais dispositivos Tuya. O LocalTuya valida cada um em sequência; dispositivos que exigem revisão do mapeamento nunca são salvos automaticamente.",
        "Dispositivos Tuya",
        "Resumo da adição em lote",
        "Adicionados automaticamente: {added_count}. Precisam de revisão: {review_count}. Falha na validação: {failed_count}. Dispositivos que precisam de revisão não foram salvos automaticamente.",
        "Selecione pelo menos um dispositivo.",
    ),
    "zh-Hans": (
        "从已关联账户批量添加设备",
        "选择多个已关联的 Tuya 设备，并在局域网上依次验证。",
        "批量添加设备",
        "选择一个或多个 Tuya 设备。LocalTuya 会依次验证；需要映射确认的设备绝不会被自动保存。",
        "Tuya 设备",
        "批量添加摘要",
        "自动添加：{added_count}。需要映射确认：{review_count}。验证失败：{failed_count}。需要确认的设备未被自动保存。",
        "请至少选择一个设备。",
    ),
}
for language, values in translations.items():
    path = Path(f"custom_components/localtuya/translations/{language}.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    menu, menu_desc, choose_title, choose_desc, choose_data, summary_title, summary_desc, error = values
    options = payload.setdefault("options", {})
    options.setdefault("error", {})["select_at_least_one_device"] = error
    steps = options.setdefault("step", {})
    add_menu = steps.setdefault("add_device_method", {})
    add_menu.setdefault("menu_options", {})["qr_bulk_choose_devices"] = menu
    add_menu.setdefault("menu_option_descriptions", {})["qr_bulk_choose_devices"] = menu_desc
    steps["qr_bulk_choose_devices"] = {
        "title": choose_title,
        "description": choose_desc,
        "data": {"qr_bulk_device_ids": choose_data},
    }
    steps["qr_bulk_summary"] = {
        "title": summary_title,
        "description": summary_desc,
        "data": {},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Cross-feature regression tests.
# ---------------------------------------------------------------------------
Path("tests/test_bulk_zero_config_integration.py").write_text('''"""Integration tests for prepared zero-config decisions used by bulk onboarding."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from homeassistant.const import CONF_ENTITIES

from custom_components.localtuya.zero_config import (
    ZeroConfigDecision,
    evaluate_prepared_zero_config,
    evaluate_zero_config,
)


class BulkZeroConfigIntegrationTests(unittest.TestCase):
    def test_high_candidate_engine_remains_auto_configurable(self):
        result = evaluate_zero_config([
            SimpleNamespace(
                confidence=SimpleNamespace(value="high"),
                config={"id": 20, "platform": "light"},
            )
        ])
        self.assertEqual(result.decision, ZeroConfigDecision.AUTO_CONFIGURE)

    def test_prepared_high_entities_need_no_review(self):
        result = evaluate_prepared_zero_config(
            {CONF_ENTITIES: [{"id": 20, "platform": "light"}]},
            [],
        )
        self.assertEqual(result.decision, ZeroConfigDecision.AUTO_CONFIGURE)
        self.assertEqual(result.entities[0]["platform"], "light")

    def test_medium_candidate_blocks_silent_save(self):
        result = evaluate_prepared_zero_config(
            {CONF_ENTITIES: [{"id": 20, "platform": "light"}]},
            [SimpleNamespace(confidence=SimpleNamespace(value="medium"))],
        )
        self.assertEqual(result.decision, ZeroConfigDecision.REVIEW_REQUIRED)
        self.assertEqual(result.entities, [])

    def test_no_prepared_entities_requires_manual_mapping(self):
        result = evaluate_prepared_zero_config({CONF_ENTITIES: []}, [])
        self.assertEqual(result.decision, ZeroConfigDecision.MANUAL_REQUIRED)


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")


# ---------------------------------------------------------------------------
# Changelog: development section only; historical releases remain unchanged.
# ---------------------------------------------------------------------------
p = Path("CHANGELOG.md")
s = p.read_text(encoding="utf-8")
if "## 6.7.0 — In development" not in s:
    section = '''## 6.7.0 — In development

Reliability, repair, gateway-child and zero-config onboarding development release. Stable `master` remains unchanged until explicit release approval.

### Reliability & Repair

- Added structured, privacy-safe Device Health checks and actionable Home Assistant Repairs.
- Added validated automatic host recovery, active LAN rediscovery, race protection and manual repair fallback.
- Added gateway-aware child host recovery without overwriting child identity or routing metadata.

### Gateway and Tuya protocol reliability

- Added gateway-child routing through parent IP/local key while preserving child `node_id` / CID and `gateway_id`.
- Added UUID-to-CID fallback only for explicitly marked subdevices with a known gateway.
- Added shared gateway transport so multiple children reuse one physical gateway connection and unsolicited status is routed by CID.
- Hardened Tuya 3.5 framing, fallback status queries and empty-decode handling.

### Zero-config and bulk onboarding

- Added fail-closed zero-config decisions: only deterministic prepared mappings are persisted without review.
- Added reachable linked-account bulk onboarding with multi-select, sequential LAN validation, per-device failure isolation and an explicit summary.
- Devices requiring mapping review or manual mapping are never silently written by bulk onboarding.
- Linked-account single-device onboarding now uses the same centralized zero-config decision and supports validated gateway children.

### Compatibility matrix

- Added bounded catalog `compatibility` metadata for protocol, transport, Home Assistant/LocalTuya version and hardware-test evidence.
- Added generated public JSON/Markdown compatibility matrices containing product-level evidence only, never Device IDs, hosts, local keys, account IDs or tokens.
- `verified` requires explicit hardware evidence; untested verified catalog confidence is downgraded in the public matrix.

### Validation

- Python 3.14 / Home Assistant 2026.9 regression suite and HACS validation are release gates for the final development SHA.


'''
    s = replace_once(s, "# Changelog\n\n", "# Changelog\n\n" + section, "6.7 changelog")
p.write_text(s, encoding="utf-8")
