"""Tests for LocalTuya diagnostics redaction."""

import unittest
from types import SimpleNamespace

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
)
from custom_components.localtuya.diagnostics import (
    CLOUD_DEVICES,
    DEVICE_CLOUD_INFO,
    DEVICE_CONFIG,
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
            "192.168.1.50",
        )

        self.assertEqual(
            result[
                CLOUD_DEVICES
            ]["device1"]["name"],
            "Kitchen Plug",
        )

    async def test_device_diagnostics_are_redacted(self):
        """Per-device diagnostics redact local keys too."""
        hass, entry = self._objects()

        device = SimpleNamespace(
            identifiers={
                (
                    DOMAIN,
                    "localtuya_device1",
                )
            }
        )

        result = (
            await async_get_device_diagnostics(
                hass,
                entry,
                device,
            )
        )

        rendered = repr(result)

        self.assertNotIn(
            "device-local-secret",
            rendered,
        )
        self.assertNotIn(
            "cloud-local-secret",
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


if __name__ == "__main__":
    unittest.main()
