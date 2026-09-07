"""Tests for QR onboarding and on-demand Tuya provisioning."""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.data_entry_flow import FlowResultType

from custom_components.localtuya.config_flow import LocaltuyaConfigFlow
from custom_components.localtuya.const import (
    CONF_DPS_STRINGS,
    CONF_LOCAL_KEY,
    CONF_NO_CLOUD,
    CONF_PROTOCOL_VERSION,
    DATA_DEVICE_CATALOG,
    DOMAIN,
)
from custom_components.localtuya.qr_onboarding import (
    CONF_QR_AUTH,
    CONF_QR_ENDPOINT,
    CONF_QR_TERMINAL_ID,
    CONF_QR_TOKEN_INFO,
    CONF_QR_USER_CODE,
    QrCloudClient,
    _base_entry_data,
    async_prepare_qr_device,
)


class FakeHass:
    """Minimal Home Assistant executor/data test double."""

    def __init__(self) -> None:
        self.data = {DOMAIN: {DATA_DEVICE_CATALOG: None}}

    async def async_add_executor_job(self, func, *args):
        return func(*args)


class QrCloudClientTests(unittest.IsolatedAsyncioTestCase):
    """Validate renewable QR account-link behavior."""

    async def test_qr_login_persists_only_sharing_session_fields(self):
        hass = FakeHass()
        login = MagicMock()
        login.qr_code.return_value = {
            "success": True,
            "result": {"qrcode": "qr-token"},
        }
        login.login_result.return_value = (
            True,
            {
                "terminal_id": "terminal",
                "endpoint": "https://example.invalid",
                "t": 1,
                "uid": "uid-1",
                "expire_time": 7200,
                "access_token": "access",
                "refresh_token": "refresh",
                "ignored": "not-persisted",
            },
        )

        with patch(
            "custom_components.localtuya.qr_onboarding.LoginControl",
            return_value=login,
        ):
            cloud = QrCloudClient(hass)
            self.assertEqual(
                await cloud.async_generate_qr("user-code"),
                "qr-token",
            )
            self.assertTrue(await cloud.async_login())

        self.assertEqual(
            cloud.auth,
            {
                CONF_QR_USER_CODE: "user-code",
                CONF_QR_TERMINAL_ID: "terminal",
                CONF_QR_ENDPOINT: "https://example.invalid",
                CONF_QR_TOKEN_INFO: {
                    "t": 1,
                    "uid": "uid-1",
                    "expire_time": 7200,
                    "access_token": "access",
                    "refresh_token": "refresh",
                },
            },
        )

    async def test_explicit_device_sync_captures_refreshed_token(self):
        hass = FakeHass()
        auth = {
            CONF_QR_USER_CODE: "user-code",
            CONF_QR_TERMINAL_ID: "terminal",
            CONF_QR_ENDPOINT: "endpoint",
            CONF_QR_TOKEN_INFO: {
                "t": 1,
                "uid": "uid-1",
                "expire_time": 1,
                "access_token": "old-access",
                "refresh_token": "refresh",
            },
        }

        device = SimpleNamespace(
            id="device-1",
            name="Kitchen Plug",
            local_key="local-key",
            product_id="product-1",
            product_name="Smart Plug",
            category="cz",
            online=True,
            support_local=True,
            node_id="",
        )

        manager = MagicMock()
        manager.device_map = {device.id: device}

        def manager_factory(*args):
            token_listener = args[-1]

            def update_device_cache():
                token_listener.update_token(
                    {
                        "t": 2,
                        "uid": "uid-1",
                        "expire_time": 7200,
                        "access_token": "new-access",
                        "refresh_token": "new-refresh",
                    }
                )

            manager.update_device_cache.side_effect = update_device_cache
            return manager

        with patch(
            "custom_components.localtuya.qr_onboarding.LoginControl"
        ), patch(
            "custom_components.localtuya.qr_onboarding.Manager",
            side_effect=manager_factory,
        ):
            cloud = QrCloudClient(hass, auth)
            devices = await cloud.async_get_devices()

        self.assertEqual(devices["device-1"][CONF_LOCAL_KEY], "local-key")
        self.assertEqual(
            cloud.auth[CONF_QR_TOKEN_INFO]["access_token"],
            "new-access",
        )
        self.assertEqual(
            cloud.auth[CONF_QR_TOKEN_INFO]["refresh_token"],
            "new-refresh",
        )

    def test_root_entry_keeps_runtime_cloud_disabled(self):
        auth = {
            CONF_QR_USER_CODE: "user-code",
            CONF_QR_TERMINAL_ID: "terminal",
            CONF_QR_ENDPOINT: "endpoint",
            CONF_QR_TOKEN_INFO: {"refresh_token": "refresh"},
        }
        data = _base_entry_data(auth)
        self.assertTrue(data[CONF_NO_CLOUD])
        self.assertEqual(data[CONF_QR_AUTH], auth)
        self.assertEqual(data["client_id"], "")
        self.assertEqual(data["client_secret"], "")


class QrProvisioningTests(unittest.IsolatedAsyncioTestCase):
    """Validate cloud identity -> LAN -> mapping provisioning."""

    async def test_prepare_device_uses_lan_and_auto_protocol(self):
        hass = FakeHass()
        cloud = MagicMock()
        cloud.async_get_datamodel = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "code": "switch_1",
                    "type": "Boolean",
                    "values": "{}",
                    "enumMap": {},
                }
            ]
        )
        cloud_device = {
            "id": "device-1",
            "name": "Kitchen Plug",
            CONF_LOCAL_KEY: "local-key",
            "product_id": "product-1",
            "product_name": "Smart Plug",
            "category": "cz",
            "support_local": True,
            "node_id": "",
        }

        with patch(
            "custom_components.localtuya.qr_onboarding._async_discovery_snapshot",
            new=AsyncMock(
                return_value={
                    "device-1": {
                        "gwId": "device-1",
                        "ip": "192.168.1.50",
                        "version": "3.4",
                        "productKey": "product-1",
                    }
                }
            ),
        ), patch(
            "custom_components.localtuya.config_flow.validate_input",
            new=AsyncMock(
                return_value=(["1 (value: True)"], "3.4")
            ),
        ):
            device_data, medium = await async_prepare_qr_device(
                hass,
                cloud,
                cloud_device,
            )

        self.assertEqual(device_data["host"], "192.168.1.50")
        self.assertEqual(device_data[CONF_PROTOCOL_VERSION], "3.4")
        self.assertEqual(device_data[CONF_DPS_STRINGS], ["1 (value: True)"])
        self.assertEqual(device_data["product_id"], "product-1")
        self.assertEqual(medium, [])
        self.assertTrue(device_data["entities"])


class QrConfigFlowTests(unittest.IsolatedAsyncioTestCase):
    """Validate the new recommended top-level setup choice."""

    async def test_user_step_is_qr_or_manual_menu(self):
        flow = LocaltuyaConfigFlow()
        result = await flow.async_step_user()
        self.assertEqual(result["type"], FlowResultType.MENU)
        self.assertEqual(
            result["menu_options"],
            ["qr_login", "manual_device"],
        )


if __name__ == "__main__":
    unittest.main()
