"""Tests for the advanced QR-onboarding manual fallback."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import voluptuous as vol
from homeassistant.data_entry_flow import FlowResultType

from custom_components.localtuya.config_flow import LocaltuyaConfigFlow
from custom_components.localtuya.const import (
    CONF_LOCAL_KEY,
    CONF_NO_CLOUD,
)


class QrManualFallbackTests(unittest.IsolatedAsyncioTestCase):
    """Manual Device ID/local_key setup must work without automatic mapping."""

    async def test_manual_setup_can_build_entity_when_catalog_has_no_match(self):
        flow = LocaltuyaConfigFlow()
        flow.hass = SimpleNamespace()

        device_input = {
            "friendly_name": "Unknown Tuya Device",
            "host": "192.168.1.60",
            "device_id": "manual-device-1",
            CONF_LOCAL_KEY: "manual-local-key",
            "protocol_version": "auto",
            "enable_debug": False,
        }

        with patch(
            "custom_components.localtuya.config_flow.validate_input",
            new=AsyncMock(
                return_value=(["1 (value: True)"], "3.4")
            ),
        ), patch(
            "custom_components.localtuya.qr_onboarding._async_discovery_snapshot",
            new=AsyncMock(return_value={}),
        ), patch(
            "custom_components.localtuya.config_flow.async_get_entity_candidates",
            new=AsyncMock(return_value=[]),
        ):
            result = await flow.async_step_manual_device(device_input)

        self.assertEqual(result["type"], FlowResultType.FORM)
        self.assertEqual(result["step_id"], "manual_pick_entity_type")

        manual_schema = vol.Schema(
            {
                vol.Required("id"): vol.In(["1 (value: True)"]),
                vol.Required("friendly_name"): str,
            }
        )

        with patch(
            "custom_components.localtuya.config_flow.platform_schema",
            new=AsyncMock(return_value=manual_schema),
        ):
            result = await flow.async_step_manual_pick_entity_type(
                {"manual_platform": "switch"}
            )
            self.assertEqual(result["step_id"], "manual_configure_entity")

            # With one available DP, configuring that entity consumes the last
            # DP and the flow completes automatically without an extra click.
            result = await flow.async_step_manual_configure_entity(
                {
                    "id": "1 (value: True)",
                    "friendly_name": "Manual Switch",
                }
            )

        self.assertEqual(result["type"], FlowResultType.CREATE_ENTRY)
        self.assertTrue(result["data"][CONF_NO_CLOUD])
        configured = result["data"]["devices"]["manual-device-1"]
        self.assertEqual(configured["protocol_version"], "3.4")
        self.assertEqual(configured[CONF_LOCAL_KEY], "manual-local-key")
        self.assertEqual(len(configured["entities"]), 1)
        self.assertEqual(configured["entities"][0]["platform"], "switch")
        self.assertEqual(configured["entities"][0]["id"], 1)


if __name__ == "__main__":
    unittest.main()
