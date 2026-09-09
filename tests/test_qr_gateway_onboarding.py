"""QR onboarding regressions for SDK addresses and gateway children."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_HOST

from custom_components.localtuya.const import (
    CONF_DPS_STRINGS,
    CONF_LOCAL_KEY,
    CONF_PROTOCOL_VERSION,
)
from custom_components.localtuya.qr_onboarding import async_prepare_qr_device


class QrGatewayOnboardingTests(unittest.IsolatedAsyncioTestCase):
    """Verify fail-closed address fallback and child gateway transport."""

    def _hass(self):
        return SimpleNamespace(
            data={"localtuya": {"device_catalog": None}}
        )

    def _cloud(self):
        return SimpleNamespace(
            async_get_datamodel=AsyncMock(return_value=[]),
        )

    async def test_sdk_ip_is_validated_when_udp_discovery_misses(self):
        """SDK-reported IP avoids a false host prompt but is never trusted blindly."""
        cloud_device = {
            "id": "device-1",
            "name": "Thermostat",
            CONF_LOCAL_KEY: "local-secret",
            "product_id": "product-1",
            "category": "wk",
            "node_id": "",
            "ip": "192.168.1.55",
        }
        validate = AsyncMock(
            return_value=(["1 (value: True)"], "3.3")
        )

        with (
            patch(
                "custom_components.localtuya.qr_onboarding._async_discovery_snapshot",
                new=AsyncMock(return_value={}),
            ),
            patch(
                "custom_components.localtuya.config_flow.validate_input",
                new=validate,
            ),
            patch(
                "custom_components.localtuya.qr_onboarding.resolve_entity_candidates",
                return_value=[],
            ),
        ):
            device_data, _ = await async_prepare_qr_device(
                self._hass(),
                self._cloud(),
                cloud_device,
            )

        self.assertEqual(device_data[CONF_HOST], "192.168.1.55")
        self.assertEqual(device_data[CONF_PROTOCOL_VERSION], "3.3")
        validated = validate.await_args.args[1]
        self.assertEqual(validated[CONF_HOST], "192.168.1.55")
        self.assertEqual(validated[CONF_LOCAL_KEY], "local-secret")

    async def test_child_uses_gateway_transport_and_keeps_child_identity(self):
        """A hub child connects through the gateway IP/key with its own node ID."""
        cloud_device = {
            "id": "child-device-1",
            "name": "Bluetooth Bulb",
            CONF_LOCAL_KEY: "",
            "product_id": "bulb-product",
            "category": "dj",
            "node_id": "node-123",
            "gateway_id": "gateway-device-1",
            "gateway_local_key": "gateway-secret",
            "gateway_ip": "192.168.1.80",
        }
        validate = AsyncMock(
            return_value=(["20 (value: True)"], "3.4")
        )

        with (
            patch(
                "custom_components.localtuya.qr_onboarding._async_discovery_snapshot",
                new=AsyncMock(return_value={}),
            ),
            patch(
                "custom_components.localtuya.config_flow.validate_input",
                new=validate,
            ),
            patch(
                "custom_components.localtuya.qr_onboarding.resolve_entity_candidates",
                return_value=[],
            ),
        ):
            device_data, _ = await async_prepare_qr_device(
                self._hass(),
                self._cloud(),
                cloud_device,
            )

        self.assertEqual(device_data["device_id"], "child-device-1")
        self.assertEqual(device_data["node_id"], "node-123")
        self.assertEqual(device_data["gateway_id"], "gateway-device-1")
        self.assertEqual(device_data[CONF_HOST], "192.168.1.80")
        self.assertEqual(device_data[CONF_LOCAL_KEY], "gateway-secret")
        self.assertEqual(device_data[CONF_PROTOCOL_VERSION], "3.4")
        self.assertEqual(
            device_data[CONF_DPS_STRINGS],
            ["20 (value: True)"],
        )

        validated = validate.await_args.args[1]
        self.assertEqual(validated["device_id"], "child-device-1")
        self.assertEqual(validated["node_id"], "node-123")
        self.assertEqual(validated["gateway_id"], "gateway-device-1")
        self.assertEqual(validated[CONF_HOST], "192.168.1.80")
        self.assertEqual(validated[CONF_LOCAL_KEY], "gateway-secret")

    async def test_child_prefers_live_gateway_discovery_over_cached_sdk_ip(self):
        """A fresh LAN discovery address wins over the SDK gateway cache."""
        cloud_device = {
            "id": "child-device-1",
            "name": "Bluetooth Bulb",
            CONF_LOCAL_KEY: "",
            "product_id": "bulb-product",
            "category": "dj",
            "node_id": "node-123",
            "gateway_id": "gateway-device-1",
            "gateway_local_key": "gateway-secret",
            "gateway_ip": "192.168.1.80",
        }
        discovered = {
            "gateway-device-1": {
                "gwId": "gateway-device-1",
                "ip": "192.168.1.81",
            }
        }
        validate = AsyncMock(
            return_value=(["20 (value: True)"], "3.4")
        )

        with (
            patch(
                "custom_components.localtuya.qr_onboarding._async_discovery_snapshot",
                new=AsyncMock(return_value=discovered),
            ),
            patch(
                "custom_components.localtuya.config_flow.validate_input",
                new=validate,
            ),
            patch(
                "custom_components.localtuya.qr_onboarding.resolve_entity_candidates",
                return_value=[],
            ),
        ):
            device_data, _ = await async_prepare_qr_device(
                self._hass(),
                self._cloud(),
                cloud_device,
            )

        self.assertEqual(device_data[CONF_HOST], "192.168.1.81")
        self.assertEqual(
            validate.await_args.args[1][CONF_HOST],
            "192.168.1.81",
        )


if __name__ == "__main__":
    unittest.main()
