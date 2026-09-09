"""Tests for the QR onboarding and provisioning-only Tuya account link."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResultType

from custom_components.localtuya.config_flow import (
    CannotConnect,
    LocaltuyaConfigFlow,
)
from custom_components.localtuya.const import (
    CONF_DPS_STRINGS,
    CONF_LOCAL_KEY,
    CONF_NO_CLOUD,
    CONF_PROTOCOL_VERSION,
)
from custom_components.localtuya.qr_onboarding import (
    CONF_QR_AUTH,
    CONF_QR_ENDPOINT,
    CONF_QR_TERMINAL_ID,
    CONF_QR_TOKEN_INFO,
    CONF_QR_USER_CODE,
    QrCloudClient,
    QrProvisioningError,
    _base_entry_data,
    async_prepare_qr_device,
)


class _FakeHass:
    """Minimal Home Assistant executor shim."""

    def __init__(self):
        self.data = {}

    async def async_add_executor_job(self, target, *args):
        return target(*args)


class _FakeLoginControl:
    """Return deterministic sharing login responses."""

    def qr_code(self, client_id, schema, user_code):
        return {
            "success": True,
            "result": {"qrcode": "qr-token"},
        }

    def login_result(self, qr_token, client_id, user_code):
        return (
            True,
            {
                CONF_QR_TERMINAL_ID: "terminal-1",
                CONF_QR_ENDPOINT: "https://example.invalid",
                "t": 1,
                "uid": "uid-1",
                "expire_time": 3600,
                "access_token": "access-1",
                "refresh_token": "refresh-1",
                "ignored": "must-not-be-persisted",
            },
        )


def _cloud_device() -> dict:
    """Return a locally eligible sharing-SDK device record."""
    return {
        "id": "device-1",
        "name": "Kitchen Plug",
        CONF_LOCAL_KEY: "local-secret",
        "product_id": "product-1",
        "product_name": "Plug",
        "category": "cz",
        "support_local": True,
        "node_id": "",
    }


def _high_candidate():
    """Return one high-confidence mapper candidate."""
    from custom_components.localtuya.device_mapper import MappingConfidence

    return SimpleNamespace(
        confidence=MappingConfidence.HIGH,
        config={
            "platform": "switch",
            "id": 1,
            "friendly_name": "Kitchen Plug",
        },
        platform="switch",
        primary_dp=1,
    )


class QrCloudClientTests(unittest.IsolatedAsyncioTestCase):
    """Validate account-link persistence and on-demand token refresh."""

    async def test_qr_login_persists_only_sharing_session_fields(self):
        hass = _FakeHass()
        cloud = QrCloudClient(hass)
        cloud._login_control = _FakeLoginControl()

        token = await cloud.async_generate_qr("user-code-1")
        self.assertEqual(token, "qr-token")
        self.assertTrue(await cloud.async_login())

        auth = cloud.auth
        self.assertEqual(auth[CONF_QR_USER_CODE], "user-code-1")
        self.assertEqual(auth[CONF_QR_TERMINAL_ID], "terminal-1")
        self.assertEqual(auth[CONF_QR_ENDPOINT], "https://example.invalid")
        self.assertEqual(
            auth[CONF_QR_TOKEN_INFO]["refresh_token"],
            "refresh-1",
        )
        self.assertNotIn("ignored", auth[CONF_QR_TOKEN_INFO])

    async def test_explicit_device_sync_captures_refreshed_token(self):
        hass = _FakeHass()
        auth = {
            CONF_QR_USER_CODE: "user-code-1",
            CONF_QR_TERMINAL_ID: "terminal-1",
            CONF_QR_ENDPOINT: "https://example.invalid",
            CONF_QR_TOKEN_INFO: {
                "access_token": "access-old",
                "refresh_token": "refresh-old",
            },
        }
        cloud = QrCloudClient(hass, auth)

        device = SimpleNamespace(
            id="device-1",
            name="Kitchen Plug",
            local_key="local-secret",
            product_id="product-1",
            product_name="Plug",
            category="cz",
            online=True,
            support_local=True,
            node_id="",
        )

        class FakeManager:
            def __init__(self, token_listener):
                self.device_map = {"device-1": device}
                self._token_listener = token_listener

            def update_device_cache(self):
                self._token_listener.update_token(
                    {
                        "access_token": "access-new",
                        "refresh_token": "refresh-new",
                    }
                )

        def build_manager():
            from custom_components.localtuya.qr_onboarding import _TokenCapture

            return FakeManager(_TokenCapture(cloud._auth))

        cloud._build_manager = build_manager
        devices = await cloud.async_get_devices()

        self.assertIn("device-1", devices)
        self.assertEqual(
            devices["device-1"][CONF_LOCAL_KEY],
            "local-secret",
        )
        self.assertEqual(
            cloud.auth[CONF_QR_TOKEN_INFO]["refresh_token"],
            "refresh-new",
        )

    def test_root_entry_keeps_runtime_cloud_disabled(self):
        auth = {
            CONF_QR_USER_CODE: "user-code-1",
            CONF_QR_TERMINAL_ID: "terminal-1",
            CONF_QR_ENDPOINT: "https://example.invalid",
            CONF_QR_TOKEN_INFO: {"refresh_token": "refresh-1"},
        }
        data = _base_entry_data(auth)

        self.assertTrue(data[CONF_NO_CLOUD])
        self.assertEqual(data[CONF_QR_AUTH], auth)
        self.assertEqual(data["client_id"], "")
        self.assertEqual(data["client_secret"], "")


class QrProvisioningTests(unittest.IsolatedAsyncioTestCase):
    """Validate cloud identity -> LAN connectivity -> mapper pipeline."""

    def _hass(self):
        return SimpleNamespace(
            data={
                "localtuya": {
                    "device_catalog": None,
                }
            }
        )

    def _cloud(self):
        return SimpleNamespace(
            async_get_datamodel=AsyncMock(
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
        )

    async def test_prepare_device_uses_lan_and_auto_protocol(self):
        hass = self._hass()
        cloud = self._cloud()
        discovered = {
            "gwId": "device-1",
            "ip": "192.168.1.50",
            "productKey": "product-1",
        }

        with patch(
            "custom_components.localtuya.qr_onboarding._async_find_lan_device",
            new=AsyncMock(return_value=discovered),
        ), patch(
            "custom_components.localtuya.config_flow.validate_input",
            new=AsyncMock(
                return_value=(["1 (value: True)"], "3.4")
            ),
        ), patch(
            "custom_components.localtuya.qr_onboarding.resolve_entity_candidates",
            return_value=[_high_candidate()],
        ):
            device_data, medium = await async_prepare_qr_device(
                hass,
                cloud,
                _cloud_device(),
            )

        self.assertEqual(device_data[CONF_HOST], "192.168.1.50")
        self.assertEqual(device_data[CONF_PROTOCOL_VERSION], "3.4")
        self.assertEqual(
            device_data[CONF_DPS_STRINGS],
            ["1 (value: True)"],
        )
        self.assertEqual(device_data["product_id"], "product-1")
        self.assertEqual(medium, [])
        self.assertTrue(device_data["entities"])
        cloud.async_get_datamodel.assert_awaited_once_with("device-1")

    async def test_missing_discovery_requests_manual_host(self):
        """Missing LAN discovery must request a manual, validated host."""
        hass = self._hass()
        cloud = self._cloud()

        with patch(
            "custom_components.localtuya.qr_onboarding._async_find_lan_device",
            new=AsyncMock(return_value=None),
        ):
            with self.assertRaises(QrProvisioningError) as ctx:
                await async_prepare_qr_device(
                    hass,
                    cloud,
                    _cloud_device(),
                )

        self.assertEqual(ctx.exception.reason, "qr_device_host_required")
        cloud.async_get_datamodel.assert_not_awaited()

    async def test_discovery_error_still_allows_manual_host_fallback(self):
        """A discovery subsystem failure still degrades to manual LAN address."""
        hass = self._hass()
        cloud = self._cloud()

        with patch(
            "custom_components.localtuya.qr_onboarding._async_find_lan_device",
            new=AsyncMock(return_value=None),
        ):
            with self.assertRaises(QrProvisioningError) as ctx:
                await async_prepare_qr_device(
                    hass,
                    cloud,
                    _cloud_device(),
                )

        self.assertEqual(ctx.exception.reason, "qr_device_host_required")

    async def test_manual_host_is_validated_before_cloud_enrichment(self):
        """A supplied host is accepted only after real LAN protocol/DPS validation."""
        hass = self._hass()
        cloud = self._cloud()
        validate = AsyncMock(
            return_value=(["1 (value: True)"], "3.5")
        )

        with patch(
            "custom_components.localtuya.qr_onboarding._async_find_lan_device",
            new=AsyncMock(
                side_effect=AssertionError(
                    "manual host must not require UDP discovery"
                )
            ),
        ), patch(
            "custom_components.localtuya.config_flow.validate_input",
            new=validate,
        ), patch(
            "custom_components.localtuya.qr_onboarding.resolve_entity_candidates",
            return_value=[_high_candidate()],
        ):
            device_data, medium = await async_prepare_qr_device(
                hass,
                cloud,
                _cloud_device(),
                host_override="10.0.21.42",
            )

        self.assertEqual(device_data[CONF_HOST], "10.0.21.42")
        self.assertEqual(device_data[CONF_PROTOCOL_VERSION], "3.5")
        self.assertEqual(medium, [])
        validate.assert_awaited_once()
        validated = validate.await_args.args[1]
        self.assertEqual(validated[CONF_HOST], "10.0.21.42")
        self.assertEqual(validated[CONF_LOCAL_KEY], "local-secret")
        cloud.async_get_datamodel.assert_awaited_once_with("device-1")

    async def test_wrong_manual_host_is_rejected_before_cloud_enrichment(self):
        """Never save or enrich a host that failed the direct LAN probe."""
        hass = self._hass()
        cloud = self._cloud()

        with patch(
            "custom_components.localtuya.config_flow.validate_input",
            new=AsyncMock(side_effect=CannotConnect()),
        ):
            with self.assertRaises(QrProvisioningError) as ctx:
                await async_prepare_qr_device(
                    hass,
                    cloud,
                    _cloud_device(),
                    host_override="10.0.21.99",
                )

        self.assertEqual(ctx.exception.reason, "cannot_connect")
        cloud.async_get_datamodel.assert_not_awaited()


class QrConfigFlowTests(unittest.IsolatedAsyncioTestCase):
    """Validate recommended setup choices and LAN fallback transitions."""

    async def test_user_step_has_qr_manual_and_import_modes(self):
        flow = LocaltuyaConfigFlow()
        result = await flow.async_step_user()
        self.assertEqual(result["type"], FlowResultType.MENU)
        self.assertEqual(
            result["menu_options"],
            ["qr_login", "manual_device", "import_existing"],
        )

    async def test_qr_device_choice_moves_to_host_fallback(self):
        flow = LocaltuyaConfigFlow()
        flow.hass = SimpleNamespace(data={})
        flow._qr_cloud = SimpleNamespace(auth={})
        flow._qr_devices = {"device-1": _cloud_device()}

        with patch(
            "custom_components.localtuya.qr_onboarding.async_prepare_qr_device",
            new=AsyncMock(
                side_effect=QrProvisioningError(
                    "qr_device_host_required",
                    "automatic discovery did not find an address",
                )
            ),
        ):
            result = await flow.async_step_qr_choose_device(
                {"device_id": "device-1"}
            )

        self.assertEqual(result["type"], FlowResultType.FORM)
        self.assertEqual(result["step_id"], "qr_device_host")

    async def test_qr_host_fallback_can_complete_first_device(self):
        """The fallback preserves cloud credentials but stores validated LAN host."""
        flow = LocaltuyaConfigFlow()
        flow.hass = SimpleNamespace(data={})
        flow._qr_cloud = SimpleNamespace(auth={})
        flow._qr_selected_device = _cloud_device()
        prepared = {
            "friendly_name": "Kitchen Plug",
            CONF_HOST: "10.0.21.42",
            "device_id": "device-1",
            CONF_LOCAL_KEY: "local-secret",
            CONF_PROTOCOL_VERSION: "3.5",
            CONF_DPS_STRINGS: ["1 (value: True)"],
            "entities": [
                {
                    "platform": "switch",
                    "id": 1,
                    "friendly_name": "Kitchen Plug",
                }
            ],
        }

        with patch(
            "custom_components.localtuya.qr_onboarding.async_prepare_qr_device",
            new=AsyncMock(return_value=(prepared, [])),
        ) as prepare:
            result = await flow.async_step_qr_device_host(
                {CONF_HOST: "10.0.21.42"}
            )

        self.assertEqual(result["type"], FlowResultType.CREATE_ENTRY)
        stored = result["data"]["devices"]["device-1"]
        self.assertEqual(stored[CONF_HOST], "10.0.21.42")
        self.assertTrue(result["data"][CONF_NO_CLOUD])
        prepare.assert_awaited_once()
        self.assertEqual(
            prepare.await_args.kwargs["host_override"],
            "10.0.21.42",
        )


if __name__ == "__main__":
    unittest.main()
