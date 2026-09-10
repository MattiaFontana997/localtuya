"""Regressions for Tuya Device Sharing hub/child metadata quirks."""

from __future__ import annotations

import unittest

from custom_components.localtuya.const import CONF_LOCAL_KEY
from custom_components.localtuya.qr_onboarding import (
    TUYA_HUB_CATEGORIES,
    _enrich_gateway_routes,
    _qr_is_locally_eligible,
)


class TuyaLocalGatewayMetadataTests(unittest.TestCase):
    def test_known_bluetooth_gateway_category_is_recognized(self):
        self.assertIn("wg2", TUYA_HUB_CATEGORIES)

    def test_single_hub_recovers_missing_gateway_id_and_prefers_child_key(self):
        devices = {
            "gateway-1": {
                "id": "gateway-1",
                "name": "Bluetooth Gateway",
                CONF_LOCAL_KEY: "hub-local-key",
                "ip": "192.168.1.20",
                "is_hub": True,
                "node_id": "",
            },
            "lamp-1": {
                "id": "lamp-1",
                "name": "BLE Lamp",
                CONF_LOCAL_KEY: "child-exposed-gateway-key",
                "node_id": "child-uuid-as-cid",
                "gateway_id": "",
                "is_hub": False,
            },
        }

        result = _enrich_gateway_routes(devices)
        child = result["lamp-1"]

        self.assertEqual(child["gateway_id"], "gateway-1")
        self.assertEqual(child["gateway_local_key"], "child-exposed-gateway-key")
        self.assertEqual(child["gateway_ip"], "192.168.1.20")
        self.assertTrue(_qr_is_locally_eligible(child))

    def test_single_hub_key_is_used_when_child_has_no_key(self):
        devices = {
            "gateway-1": {
                "id": "gateway-1",
                CONF_LOCAL_KEY: "hub-local-key",
                "ip": "192.168.1.20",
                "is_hub": True,
                "node_id": "",
            },
            "lamp-1": {
                "id": "lamp-1",
                CONF_LOCAL_KEY: "",
                "node_id": "cid-1",
                "gateway_id": "",
                "is_hub": False,
            },
        }

        child = _enrich_gateway_routes(devices)["lamp-1"]
        self.assertEqual(child["gateway_local_key"], "hub-local-key")
        self.assertTrue(_qr_is_locally_eligible(child))

    def test_multiple_hubs_keep_child_selectable_for_explicit_parent(self):
        """Ambiguous children remain visible but no parent is guessed."""
        devices = {
            "gateway-1": {
                "id": "gateway-1",
                CONF_LOCAL_KEY: "key-1",
                "is_hub": True,
            },
            "gateway-2": {
                "id": "gateway-2",
                CONF_LOCAL_KEY: "key-2",
                "is_hub": True,
            },
            "lamp-1": {
                "id": "lamp-1",
                CONF_LOCAL_KEY: "child-key",
                "node_id": "cid-1",
                "gateway_id": "",
                "is_hub": False,
            },
        }

        child = _enrich_gateway_routes(devices)["lamp-1"]
        self.assertFalse(child.get("gateway_id"))
        self.assertEqual(child["gateway_candidates"], ["gateway-1", "gateway-2"])
        self.assertTrue(_qr_is_locally_eligible(child))


if __name__ == "__main__":
    unittest.main()
