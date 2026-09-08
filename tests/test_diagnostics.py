"""Tests for LocalTuya diagnostics redaction."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICES,
)

from custom_components.localtuya.const import (
    CONF_LOCAL_KEY,
    CONF_USER_ID,
    DATA_CLOUD,
    DOMAIN,
    TUYA_DEVICES,
)
from custom_components.localtuya.device_health import (
    DeviceHealthReport,
    DeviceHealthStage,
)
from custom_components.localtuya.diagnostics import (
    CLOUD_DEVICES,
    DEVICE_CLOUD_INFO,
    DEVICE_CONFIG,
    DEVICE_HEALTH_DIAGNOSTICS,
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)


class DiagnosticsTests(
    unittest.IsolatedAsyncioTestCase
):
    """Test diagnostic output and secret redaction."""

    @staticmethod
    def _objects():
        cloud = SimpleNamespace(
            device_list={
                "device1": {
                    "id": "device1",
                    "name": "Kitchen Plug",
                    CONF_LOCAL_KEY:
                        "cloud-local-secret",
                }
            }
        )

        hass = SimpleNamespace(
            data={
                DOMAIN: {
                    DATA_CLOUD: cloud,
                    TUYA_DEVICES: {
                        "device1": SimpleNamespace(
                            connected=True,
                        ),
                    },
                }
            }
        )

        entry = SimpleNamespace(
            data={
                CONF_CLIENT_ID:
                    "client-secret-value",
                CONF_CLIENT_SECRET:
                    "api-secret-value",
                CONF_USER_ID:
                    "user-secret-value",
                CONF_DEVICES: {
                    "device1": {
                        "friendly_name":
                            "Kitchen Plug",
                        "host":
                            "192.168.1.50",
                        CONF_LOCAL_KEY:
                            "device-local-secret",
                    }
                },
            }
        )

        return hass, entry

    @staticmethod
    def _device():
        return SimpleNamespace(
            identifiers={
                (
                    DOMAIN,
                    "localtuya_device1",
                )
            }
        )

    async def test_config_entry_secrets_are_redacted(self):
        """Account and device secrets never leak into diagnostics."""
        hass, entry = self._objects()

        result = (
            await async_get_config_entry_diagnostics(
                hass,
                entry,
            )
        )

        rendered = repr(result)

        for secret in (
            "client-secret-value",
            "api-secret-value",
            "user-secret-value",
            "device-local-secret",
            "cloud-local-secret",
        ):
            self.assertNotIn(
                secret,
                rendered,
            )

        self.assertEqual(
            result[
                CONF_DEVICES
            ]["device1"]["host"],
            "**REDACTED**",
        )

        self.assertNotIn(
            "192.168.1.50",
            rendered,
        )

        self.assertEqual(
            result[
                CLOUD_DEVICES
            ]["device1"]["name"],
            "Kitchen Plug",
        )

    async def test_device_diagnostics_are_redacted(self):
        """Per-device diagnostics include live health without leaking secrets."""
        hass, entry = self._objects()
        device = self._device()
        report = DeviceHealthReport(
            requested_protocol="3.5",
            resolved_protocol="3.5",
            stage=DeviceHealthStage.READY,
            detected_dps={
                "1": "raw-dp-secret",
                "20": True,
            },
        )

        with patch(
            "custom_components.localtuya.diagnostics.async_device_preflight",
            new=AsyncMock(return_value=report),
        ) as preflight:
            result = (
                await async_get_device_diagnostics(
                    hass,
                    entry,
                    device,
                )
            )

        rendered = repr(result)

        for secret in (
            "device-local-secret",
            "cloud-local-secret",
            "raw-dp-secret",
            "192.168.1.50",
            "device1",
        ):
            self.assertNotIn(
                secret,
                rendered,
            )

        self.assertEqual(
            result[
                DEVICE_CONFIG
            ]["friendly_name"],
            "Kitchen Plug",
        )

        self.assertEqual(
            result[
                DEVICE_CLOUD_INFO
            ]["name"],
            "Kitchen Plug",
        )

        health = result[
            DEVICE_HEALTH_DIAGNOSTICS
        ]
        self.assertTrue(
            health["runtime_present"]
        )
        self.assertTrue(
            health["runtime_connected"]
        )
        self.assertTrue(
            health["preflight"]["ok"]
        )
        self.assertEqual(
            health["preflight"]["resolved_protocol"],
            "3.5",
        )
        self.assertEqual(
            health["preflight"]["dp_ids"],
            [1, 20],
        )
        self.assertNotIn(
            "detected_dps",
            health["preflight"],
        )

        preflight.assert_awaited_once()
        probe_data = preflight.await_args.args[1]
        self.assertEqual(
            probe_data["device_id"],
            "device1",
        )
        self.assertEqual(
            probe_data[CONF_LOCAL_KEY],
            "device-local-secret",
        )

    async def test_health_probe_error_keeps_diagnostics_private_and_available(self):
        """Probe failures expose only an exception class, never its message."""
        hass, entry = self._objects()
        secret_message = (
            "host=192.168.1.50 local_key=device-local-secret device=device1"
        )

        with patch(
            "custom_components.localtuya.diagnostics.async_device_preflight",
            new=AsyncMock(
                side_effect=RuntimeError(
                    secret_message
                )
            ),
        ):
            result = (
                await async_get_device_diagnostics(
                    hass,
                    entry,
                    self._device(),
                )
            )

        health = result[
            DEVICE_HEALTH_DIAGNOSTICS
        ]
        self.assertIsNone(
            health["preflight"]
        )
        self.assertEqual(
            health["probe_error_type"],
            "RuntimeError",
        )

        rendered = repr(result)
        self.assertNotIn(
            secret_message,
            rendered,
        )
        self.assertNotIn(
            "device-local-secret",
            rendered,
        )
        self.assertNotIn(
            "192.168.1.50",
            rendered,
        )
        self.assertNotIn(
            "device1",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()
