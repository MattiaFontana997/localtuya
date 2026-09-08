"""Tests for legacy cloud compatibility and QR-link visibility."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICES,
)
import voluptuous as vol

from custom_components.localtuya.config_flow import (
    LINK_QR_ACCOUNT,
    LocalTuyaOptionsFlowHandler,
)
from custom_components.localtuya.const import (
    CONF_ACTION,
    CONF_ADD_DEVICE,
    CONF_NO_CLOUD,
    CONF_SETUP_CLOUD,
    CONF_USER_ID,
)
from custom_components.localtuya.qr_onboarding import CONF_QR_AUTH


class _OptionsFlowUnderTest(LocalTuyaOptionsFlowHandler):
    """Expose a deterministic config entry without the HA flow manager."""

    @property
    def config_entry(self):
        return self._test_entry


class LegacyCloudVisibilityTests(unittest.IsolatedAsyncioTestCase):
    """Expose only account actions appropriate for the stored entry type."""

    async def _schema_for(self, data):
        entry = SimpleNamespace(data=data)
        flow = _OptionsFlowUnderTest(entry)
        flow._test_entry = entry
        flow.hass = SimpleNamespace()
        labels = {
            CONF_ADD_DEVICE: "Add a new device",
            CONF_SETUP_CLOUD: "Reconfigure Cloud API account",
            LINK_QR_ACCOUNT: "Link Smart Life / Tuya account by QR",
        }
        with patch(
            "custom_components.localtuya.config_flow._async_action_labels",
            new=AsyncMock(return_value=labels),
        ):
            result = await flow.async_step_init()
        return result["data_schema"]

    async def test_new_manual_entry_hides_developer_platform_and_offers_qr_link(self):
        schema = await self._schema_for(
            {
                CONF_NO_CLOUD: True,
                CONF_CLIENT_ID: "",
                CONF_CLIENT_SECRET: "",
                CONF_QR_AUTH: {},
            }
        )

        self.assertEqual(
            schema({CONF_ACTION: CONF_ADD_DEVICE})[CONF_ACTION],
            CONF_ADD_DEVICE,
        )
        self.assertEqual(
            schema({CONF_ACTION: LINK_QR_ACCOUNT})[CONF_ACTION],
            LINK_QR_ACCOUNT,
        )
        with self.assertRaises(vol.Invalid):
            schema({CONF_ACTION: CONF_SETUP_CLOUD})

    async def test_linked_qr_entry_hides_redundant_top_level_link_action(self):
        schema = await self._schema_for(
            {
                CONF_NO_CLOUD: True,
                CONF_CLIENT_ID: "",
                CONF_CLIENT_SECRET: "",
                CONF_QR_AUTH: {"user_code": "linked"},
            }
        )

        with self.assertRaises(vol.Invalid):
            schema({CONF_ACTION: LINK_QR_ACCOUNT})

    async def test_existing_legacy_cloud_entry_keeps_compatibility_action(self):
        schema = await self._schema_for(
            {
                CONF_NO_CLOUD: False,
                CONF_CLIENT_ID: "legacy-client-id",
                CONF_CLIENT_SECRET: "legacy-secret",
                CONF_QR_AUTH: {},
            }
        )

        self.assertEqual(
            schema({CONF_ACTION: CONF_SETUP_CLOUD})[CONF_ACTION],
            CONF_SETUP_CLOUD,
        )
        self.assertEqual(
            schema({CONF_ACTION: LINK_QR_ACCOUNT})[CONF_ACTION],
            LINK_QR_ACCOUNT,
        )

    async def test_qr_link_migrates_legacy_entry_to_lan_only(self):
        """Opting into QR removes Developer Platform runtime credentials."""
        devices = {
            "device-1": {
                "friendly_name": "Existing Plug",
                "host": "192.168.1.40",
                "local_key": "existing-local-key",
            }
        }
        entry = SimpleNamespace(
            data={
                CONF_NO_CLOUD: False,
                CONF_CLIENT_ID: "legacy-client-id",
                CONF_CLIENT_SECRET: "legacy-secret",
                CONF_USER_ID: "legacy-user-id",
                CONF_DEVICES: devices,
                CONF_QR_AUTH: {},
            }
        )
        flow = _OptionsFlowUnderTest(entry)
        flow._test_entry = entry
        flow.hass = SimpleNamespace(
            config_entries=SimpleNamespace(
                async_update_entry=lambda target, data: setattr(
                    target,
                    "data",
                    data,
                )
            )
        )
        auth = {
            "user_code": "qr-user",
            "token_info": {"refresh_token": "refresh-token"},
        }

        flow._persist_qr_auth(auth)

        self.assertTrue(entry.data[CONF_NO_CLOUD])
        self.assertEqual(entry.data[CONF_CLIENT_ID], "")
        self.assertEqual(entry.data[CONF_CLIENT_SECRET], "")
        self.assertEqual(entry.data[CONF_USER_ID], "")
        self.assertEqual(entry.data[CONF_QR_AUTH], auth)
        self.assertEqual(entry.data[CONF_DEVICES], devices)


if __name__ == "__main__":
    unittest.main()
