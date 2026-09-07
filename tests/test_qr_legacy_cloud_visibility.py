"""Tests for legacy Tuya Developer Platform compatibility visibility."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
import voluptuous as vol

from custom_components.localtuya.config_flow import LocalTuyaOptionsFlowHandler
from custom_components.localtuya.const import (
    CONF_ACTION,
    CONF_ADD_DEVICE,
    CONF_NO_CLOUD,
    CONF_SETUP_CLOUD,
)


class _OptionsFlowUnderTest(LocalTuyaOptionsFlowHandler):
    """Expose a deterministic config entry without the HA flow manager."""

    @property
    def config_entry(self):
        return self._test_entry


class LegacyCloudVisibilityTests(unittest.IsolatedAsyncioTestCase):
    """Developer Platform setup must not appear in the new standard UX."""

    async def _schema_for(self, data):
        entry = SimpleNamespace(data=data)
        flow = _OptionsFlowUnderTest(entry)
        flow._test_entry = entry
        flow.hass = SimpleNamespace()
        labels = {
            CONF_ADD_DEVICE: "Add a new device",
            CONF_SETUP_CLOUD: "Reconfigure Cloud API account",
        }
        with patch(
            "custom_components.localtuya.config_flow._async_action_labels",
            new=AsyncMock(return_value=labels),
        ):
            result = await flow.async_step_init()
        return result["data_schema"]

    async def test_new_qr_or_manual_entry_hides_developer_platform(self):
        schema = await self._schema_for(
            {
                CONF_NO_CLOUD: True,
                CONF_CLIENT_ID: "",
                CONF_CLIENT_SECRET: "",
            }
        )

        self.assertEqual(
            schema({CONF_ACTION: CONF_ADD_DEVICE})[CONF_ACTION],
            CONF_ADD_DEVICE,
        )
        with self.assertRaises(vol.Invalid):
            schema({CONF_ACTION: CONF_SETUP_CLOUD})

    async def test_existing_legacy_cloud_entry_keeps_compatibility_action(self):
        schema = await self._schema_for(
            {
                CONF_NO_CLOUD: False,
                CONF_CLIENT_ID: "legacy-client-id",
                CONF_CLIENT_SECRET: "legacy-secret",
            }
        )

        self.assertEqual(
            schema({CONF_ACTION: CONF_SETUP_CLOUD})[CONF_ACTION],
            CONF_SETUP_CLOUD,
        )


if __name__ == "__main__":
    unittest.main()
