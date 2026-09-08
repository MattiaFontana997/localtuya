from pathlib import Path
import json

config_path = Path("custom_components/localtuya/config_flow.py")
config = config_path.read_text()
old_menu = '''            menu_options=[
                "qr_login",
                "manual_device",
            ],'''
new_menu = '''            menu_options=[
                "qr_login",
                "manual_device",
                "import_existing",
            ],'''
if old_menu not in config:
    raise SystemExit("config flow user menu anchor not found")
config_path.write_text(config.replace(old_menu, new_menu, 1))

qr_path = Path("custom_components/localtuya/qr_onboarding.py")
qr = qr_path.read_text()
old_selector = '''from homeassistant.helpers.selector import (
    QrCodeSelector,
    QrCodeSelectorConfig,
    QrErrorCorrectionLevel,
)'''
new_selector = '''from homeassistant.helpers.selector import (
    QrCodeSelector,
    QrCodeSelectorConfig,
    QrErrorCorrectionLevel,
    TextSelector,
    TextSelectorConfig,
)'''
if old_selector not in qr:
    raise SystemExit("selector import anchor not found")
qr = qr.replace(old_selector, new_selector, 1)
old_constants = '''CONF_QR_TOKEN_INFO = "token_info"

TUYA_CLIENT_ID'''
new_constants = '''CONF_QR_TOKEN_INFO = "token_info"
CONF_IMPORT_JSON = "import_json"
CONF_IMPORT_DEVICE_ID = "import_device_id"

TUYA_CLIENT_ID'''
if old_constants not in qr:
    raise SystemExit("QR constants anchor not found")
qr = qr.replace(old_constants, new_constants, 1)
anchor = '''class QrConfigFlowMixin:
    """Config-flow steps for recommended QR onboarding and manual fallback."""
'''
insert = r'''def _normalize_import_device(raw: dict[str, Any], device_id_hint: str | None = None) -> dict[str, Any]:
    """Normalize supported LocalTuya/Tuya/TinyTuya device export shapes."""
    if not isinstance(raw, dict):
        raise ValueError("device must be an object")
    device_id = str(raw.get(CONF_DEVICE_ID) or raw.get("id") or raw.get("dev_id") or device_id_hint or "").strip()
    local_key = str(raw.get(CONF_LOCAL_KEY) or raw.get("localKey") or raw.get("key") or "").strip()
    if not device_id or not local_key:
        raise QrProvisioningError("import_missing_credentials", "Device ID and local_key are required")
    host = str(raw.get(CONF_HOST) or raw.get("ip") or "").strip()
    name = str(raw.get(CONF_FRIENDLY_NAME) or raw.get(CONF_NAME) or raw.get("product_name") or device_id).strip()
    protocol = str(raw.get(CONF_PROTOCOL_VERSION) or raw.get("version") or raw.get("protocol") or "auto").strip()
    if protocol not in {"auto", "3.1", "3.2", "3.3", "3.4", "3.5"}:
        protocol = "auto"
    result: dict[str, Any] = {
        CONF_FRIENDLY_NAME: name or device_id,
        CONF_HOST: host,
        CONF_DEVICE_ID: device_id,
        CONF_LOCAL_KEY: local_key,
        CONF_PROTOCOL_VERSION: protocol,
        CONF_ENABLE_DEBUG: bool(raw.get(CONF_ENABLE_DEBUG, False)),
    }
    product_key = raw.get(CONF_PRODUCT_KEY) or raw.get("productKey") or raw.get("product_id") or raw.get("productId")
    if product_key:
        result[CONF_PRODUCT_KEY] = str(product_key)
    product_id = raw.get("product_id") or raw.get("productId")
    if product_id:
        result["product_id"] = str(product_id)
    for key in ("scan_interval", "manual_dps", "reset_dpids", "model"):
        if key in raw and raw[key] is not None:
            result[key] = copy.deepcopy(raw[key])
    entities = raw.get(CONF_ENTITIES)
    if isinstance(entities, list):
        result[CONF_ENTITIES] = [copy.deepcopy(entity) for entity in entities if isinstance(entity, dict)]
    return result


def _parse_import_payload(value: str) -> dict[str, dict[str, Any]]:
    """Parse one device, a device list, or a LocalTuya root devices object."""
    try:
        payload = json.loads(str(value or ""))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON") from exc
    records: dict[str, dict[str, Any]] = {}
    def add(raw: Any, hint: str | None = None) -> None:
        if not isinstance(raw, dict):
            return
        device = _normalize_import_device(raw, hint)
        records[device[CONF_DEVICE_ID]] = device
    if isinstance(payload, dict) and isinstance(payload.get(CONF_DEVICES), dict):
        for device_id, raw in payload[CONF_DEVICES].items():
            add(raw, str(device_id))
    elif isinstance(payload, list):
        for raw in payload:
            add(raw)
    elif isinstance(payload, dict):
        add(payload)
    else:
        raise ValueError("unsupported JSON root")
    if not records:
        raise ValueError("no devices found")
    return records


class QrConfigFlowMixin:
    """Config-flow steps for recommended QR onboarding and manual fallback."""

    def _import_schema(self):
        source = getattr(self, "_import_source", "")
        return vol.Schema({vol.Required(CONF_IMPORT_JSON, default=source): TextSelector(TextSelectorConfig(multiline=True))})

    async def async_step_import_existing(self, user_input=None):
        """Import existing Device ID/local_key configuration without Tuya login."""
        errors = {}
        placeholders = {}
        if user_input is not None:
            self._import_source = str(user_input.get(CONF_IMPORT_JSON, ""))
            try:
                self._import_devices = _parse_import_payload(self._import_source)
            except QrProvisioningError as exc:
                errors["base"] = exc.reason
                placeholders = {"msg": exc.detail}
            except ValueError:
                errors["base"] = "import_invalid"
            else:
                if len(self._import_devices) == 1:
                    return await self._async_start_import_device(next(iter(self._import_devices.values())))
                return await self.async_step_import_choose_device()
        return self.async_show_form(step_id="import_existing", data_schema=self._import_schema(), errors=errors, description_placeholders=placeholders)

    async def async_step_import_choose_device(self, user_input=None):
        devices = getattr(self, "_import_devices", {})
        if not devices:
            return await self.async_step_import_existing()
        labels = {
            device_id: f"{device.get(CONF_FRIENDLY_NAME) or device_id} ({device.get(CONF_HOST) or 'LAN discovery'})"
            for device_id, device in devices.items()
        }
        if user_input is not None:
            return await self._async_start_import_device(devices[user_input[CONF_IMPORT_DEVICE_ID]])
        return self.async_show_form(
            step_id="import_choose_device",
            data_schema=vol.Schema({vol.Required(CONF_IMPORT_DEVICE_ID): vol.In(labels)}),
        )

    async def _async_start_import_device(self, imported: dict[str, Any]):
        from .config_flow import CannotConnect, EmptyDpsList, InvalidAuth, async_get_entity_candidates, validate_input
        device_data = copy.deepcopy(imported)
        device_id = device_data[CONF_DEVICE_ID]
        try:
            discovery = {}
            if not device_data.get(CONF_HOST):
                discovery = await _async_discovery_snapshot(self.hass)
                discovered = _find_discovered_device(discovery, device_id)
                if discovered is None or not discovered.get("ip"):
                    raise QrProvisioningError("import_device_not_on_lan", "The imported device was not found on the Home Assistant LAN")
                device_data[CONF_HOST] = discovered["ip"]
            dps_strings, resolved = await validate_input(self.hass, device_data)
            device_data[CONF_PROTOCOL_VERSION] = resolved
            device_data[CONF_DPS_STRINGS] = list(dps_strings)
            existing_entities = device_data.get(CONF_ENTITIES)
            self._manual_device_data = device_data
            self._manual_dps_strings = list(dps_strings)
            self._manual_entities = copy.deepcopy(existing_entities) if isinstance(existing_entities, list) else []
            if self._manual_entities:
                return self._finish_manual_initial_device()
            if not discovery:
                try:
                    discovery = await _async_discovery_snapshot(self.hass)
                except QrProvisioningError:
                    discovery = {}
            self._manual_candidates = list(await async_get_entity_candidates(self.hass, device_data, discovery, dps_strings))
            if self._manual_candidates:
                return await self.async_step_manual_mapping_review()
            return await self.async_step_manual_pick_entity_type()
        except CannotConnect:
            error, placeholders = "cannot_connect", {}
        except InvalidAuth:
            error, placeholders = "invalid_auth", {}
        except EmptyDpsList:
            error, placeholders = "empty_dps", {}
        except QrProvisioningError as exc:
            error, placeholders = exc.reason, {"msg": exc.detail}
        except Exception as exc:
            _LOGGER.exception("Unexpected imported-device validation failure: %s", exc)
            error, placeholders = "unknown", {}
        return self.async_show_form(
            step_id="import_existing",
            data_schema=self._import_schema(),
            errors={"base": error},
            description_placeholders=placeholders,
        )
'''
if anchor not in qr:
    raise SystemExit("QR config mixin anchor not found")
qr_path.write_text(qr.replace(anchor, insert, 1))

translations = {
    "en": ["Import existing configuration / local key", "Reuse an existing LocalTuya/Tuya JSON configuration or Device ID/local_key export.", "Import existing configuration", "Paste a device JSON object, a list of devices, or a LocalTuya configuration containing a devices object. LocalTuya validates the credentials and LAN connection before saving.", "Configuration JSON", "Choose imported device", "The imported data contains multiple devices. Choose the device to add now.", "Imported device", "The pasted JSON does not contain a supported device configuration.", "The imported device is missing Device ID or local_key. {msg}", "The imported device was not found on the Home Assistant LAN. {msg}"],
    "it": ["Importa configurazione / local key esistente", "Riutilizza una configurazione JSON LocalTuya/Tuya esistente o un export con Device ID e local_key.", "Importa configurazione esistente", "Incolla un dispositivo JSON, una lista di dispositivi o una configurazione LocalTuya contenente l'oggetto devices. LocalTuya verifica credenziali e connessione LAN prima di salvare.", "Configurazione JSON", "Scegli dispositivo importato", "I dati importati contengono più dispositivi. Scegli il dispositivo da aggiungere ora.", "Dispositivo importato", "Il JSON incollato non contiene una configurazione dispositivo supportata.", "Nel dispositivo importato manca Device ID o local_key. {msg}", "Il dispositivo importato non è stato trovato nella LAN di Home Assistant. {msg}"],
    "de": ["Vorhandene Konfiguration / Local Key importieren", "Eine vorhandene LocalTuya/Tuya-JSON-Konfiguration oder einen Export mit Device ID und local_key wiederverwenden.", "Vorhandene Konfiguration importieren", "Füge ein Geräte-JSON, eine Geräteliste oder eine LocalTuya-Konfiguration mit einem devices-Objekt ein. LocalTuya prüft Zugangsdaten und LAN-Verbindung vor dem Speichern.", "Konfigurations-JSON", "Importiertes Gerät auswählen", "Die importierten Daten enthalten mehrere Geräte. Wähle das Gerät aus, das jetzt hinzugefügt werden soll.", "Importiertes Gerät", "Das eingefügte JSON enthält keine unterstützte Gerätekonfiguration.", "Dem importierten Gerät fehlt Device ID oder local_key. {msg}", "Das importierte Gerät wurde im Home-Assistant-LAN nicht gefunden. {msg}"],
    "pt-BR": ["Importar configuração / local key existente", "Reutilize uma configuração JSON existente do LocalTuya/Tuya ou uma exportação com Device ID e local_key.", "Importar configuração existente", "Cole um objeto JSON de dispositivo, uma lista de dispositivos ou uma configuração LocalTuya contendo o objeto devices. O LocalTuya valida as credenciais e a conexão LAN antes de salvar.", "JSON da configuração", "Escolher dispositivo importado", "Os dados importados contêm vários dispositivos. Escolha o dispositivo para adicionar agora.", "Dispositivo importado", "O JSON colado não contém uma configuração de dispositivo compatível.", "O dispositivo importado não possui Device ID ou local_key. {msg}", "O dispositivo importado não foi encontrado na LAN do Home Assistant. {msg}"],
    "zh-Hans": ["导入现有配置 / local key", "复用现有 LocalTuya/Tuya JSON 配置，或包含 Device ID 和 local_key 的导出数据。", "导入现有配置", "粘贴单个设备 JSON、设备列表，或包含 devices 对象的 LocalTuya 配置。LocalTuya 会在保存前验证凭据和局域网连接。", "配置 JSON", "选择导入的设备", "导入数据中包含多个设备。请选择现在要添加的设备。", "导入的设备", "粘贴的 JSON 不包含受支持的设备配置。", "导入的设备缺少 Device ID 或 local_key。{msg}", "在 Home Assistant 局域网中未找到导入的设备。{msg}"],
}
for lang, text in translations.items():
    path = Path(f"custom_components/localtuya/translations/{lang}.json")
    data = json.loads(path.read_text())
    cfg = data["config"]
    user = cfg["step"]["user"]
    user["menu_options"]["import_existing"] = text[0]
    user["menu_option_descriptions"]["import_existing"] = text[1]
    cfg["error"]["import_invalid"] = text[8]
    cfg["error"]["import_missing_credentials"] = text[9]
    cfg["error"]["import_device_not_on_lan"] = text[10]
    cfg["step"]["import_existing"] = {"title": text[2], "description": text[3], "data": {"import_json": text[4]}}
    cfg["step"]["import_choose_device"] = {"title": text[5], "description": text[6], "data": {"import_device_id": text[7]}}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n")

Path("tests/test_qr_import_onboarding.py").write_text(r'''"""Tests for existing configuration import onboarding."""
from __future__ import annotations
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from homeassistant.data_entry_flow import FlowResultType
from custom_components.localtuya.config_flow import LocaltuyaConfigFlow
from custom_components.localtuya.const import CONF_LOCAL_KEY, CONF_NO_CLOUD
from custom_components.localtuya.qr_onboarding import _parse_import_payload

class QrImportParsingTests(unittest.TestCase):
    def test_localtuya_root_devices_object(self):
        devices = _parse_import_payload(json.dumps({"devices": {"device-a": {"friendly_name": "Kitchen Plug", "host": "192.168.1.30", "local_key": "secret-a", "protocol_version": "3.4"}}}))
        self.assertEqual(set(devices), {"device-a"})
        self.assertEqual(devices["device-a"][CONF_LOCAL_KEY], "secret-a")

    def test_tinytuya_aliases_are_supported(self):
        devices = _parse_import_payload(json.dumps([{"id": "device-b", "key": "secret-b", "ip": "192.168.1.31", "version": "3.3", "name": "Desk Lamp"}]))
        self.assertEqual(devices["device-b"]["host"], "192.168.1.31")
        self.assertEqual(devices["device-b"]["protocol_version"], "3.3")

class QrImportFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_user_menu_exposes_three_onboarding_modes(self):
        result = await LocaltuyaConfigFlow().async_step_user()
        self.assertEqual(result["menu_options"], ["qr_login", "manual_device", "import_existing"])

    async def test_import_preserves_existing_entities_after_validation(self):
        flow = LocaltuyaConfigFlow(); flow.hass = SimpleNamespace(data={})
        payload = json.dumps({"device_id": "device-c", "local_key": "secret-c", "host": "192.168.1.32", "protocol_version": "auto", "friendly_name": "Existing Switch", "entities": [{"platform": "switch", "id": 1, "friendly_name": "Power"}]})
        with patch("custom_components.localtuya.config_flow.validate_input", new=AsyncMock(return_value=(["1 (value: True)"], "3.4"))):
            result = await flow.async_step_import_existing({"import_json": payload})
        self.assertEqual(result["type"], FlowResultType.CREATE_ENTRY)
        self.assertTrue(result["data"][CONF_NO_CLOUD])
        device = result["data"]["devices"]["device-c"]
        self.assertEqual(device["protocol_version"], "3.4")
        self.assertEqual(device[CONF_LOCAL_KEY], "secret-c")
        self.assertEqual(device["entities"][0]["platform"], "switch")

    async def test_import_without_host_uses_lan_discovery(self):
        flow = LocaltuyaConfigFlow(); flow.hass = SimpleNamespace(data={})
        payload = json.dumps({"id": "device-d", "key": "secret-d", "name": "Imported Plug", "entities": [{"platform": "switch", "id": 1, "friendly_name": "Power"}]})
        discovery = {"device-d": {"gwId": "device-d", "ip": "192.168.1.33"}}
        with patch("custom_components.localtuya.qr_onboarding._async_discovery_snapshot", new=AsyncMock(return_value=discovery)), patch("custom_components.localtuya.config_flow.validate_input", new=AsyncMock(return_value=(["1 (value: True)"], "3.3"))):
            result = await flow.async_step_import_existing({"import_json": payload})
        device = result["data"]["devices"]["device-d"]
        self.assertEqual(device["host"], "192.168.1.33")
        self.assertEqual(device["protocol_version"], "3.3")

if __name__ == "__main__":
    unittest.main()
''')

for doc_name in ("docs/QR_ONBOARDING.md", "docs/QR_ONBOARDING_TEST_PLAN.md"):
    path = Path(doc_name)
    if not path.exists():
        continue
    text = path.read_text()
    marker = "\n## Existing configuration import\n"
    if marker in text:
        continue
    if doc_name.endswith("QR_ONBOARDING.md"):
        text += marker + "The third onboarding mode accepts a single device JSON object, a list of devices, a LocalTuya `devices` object, or common Tuya/TinyTuya aliases (`id`, `key`, `ip`, `version`). Imported credentials are validated over LAN before they are saved. Existing entity definitions are preserved; otherwise Catalog/mapper suggestions and the manual fallback are used.\n"
    else:
        text += marker + "- Import a LocalTuya root `devices` object and confirm Device ID/local_key normalization.\n- Import an `id/key/ip/version` record and confirm alias normalization.\n- Import without an IP and confirm LAN discovery supplies the host before validation.\n- Confirm invalid JSON or missing Device ID/local_key is rejected without logging secrets.\n"
    path.write_text(text)
