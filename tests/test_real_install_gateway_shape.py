"""Regression for the reported Bluetooth gateway + five child shape."""

from __future__ import annotations

import unittest

from custom_components.localtuya.const import CONF_LOCAL_KEY
from custom_components.localtuya.qr_onboarding import (
    _enrich_gateway_routes,
    _qr_is_locally_eligible,
)


class ReportedGatewayShapeTests(unittest.TestCase):
    """A single Tuya hub must make five BLE children locally routable."""

    def test_one_gateway_five_children_without_gateway_id(self):
        devices = {
            "gateway": {
                "id": "gateway",
                "name": "Bluetooth Gateway",
                CONF_LOCAL_KEY: "gateway-key",
                "ip": "192.168.1.50",
                "is_hub": True,
                "node_id": "",
            }
        }
        for index in range(1, 6):
            devices[f"lamp-{index}"] = {
                "id": f"lamp-{index}",
                "name": f"BLE Lamp {index}",
                # Device Sharing may expose the gateway LAN key on each child.
                CONF_LOCAL_KEY: "gateway-key",
                "node_id": f"lamp-cid-{index}",
                "gateway_id": "",
                "is_hub": False,
            }

        routed = _enrich_gateway_routes(devices)

        for index in range(1, 6):
            child = routed[f"lamp-{index}"]
            self.assertEqual(child["gateway_id"], "gateway")
            self.assertEqual(child["gateway_local_key"], "gateway-key")
            self.assertEqual(child["gateway_ip"], "192.168.1.50")
            self.assertEqual(child["node_id"], f"lamp-cid-{index}")
            self.assertTrue(_qr_is_locally_eligible(child))


if __name__ == "__main__":
    unittest.main()
