"""Tests for existing configuration import onboarding."""
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
