"""Regression tests for QR onboarding diagnostic privacy."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from homeassistant.const import CONF_DEVICES

from custom_components.localtuya.const import DATA_CLOUD, DOMAIN
from custom_components.localtuya.diagnostics import async_get_config_entry_diagnostics
from custom_components.localtuya.qr_onboarding import CONF_QR_AUTH


class QrDiagnosticsRedactionTests(unittest.IsolatedAsyncioTestCase):
    """Ensure renewable Tuya authorization never leaks into diagnostics."""

    async def test_qr_account_authorization_is_fully_redacted(self):
        cloud = SimpleNamespace(device_list={})
        hass = SimpleNamespace(data={DOMAIN: {DATA_CLOUD: cloud}})
        entry = SimpleNamespace(
            data={
                CONF_DEVICES: {},
                CONF_QR_AUTH: {
                    "user_code": "user-code-secret",
                    "terminal_id": "terminal-secret",
                    "endpoint": "https://secret-endpoint.invalid",
                    "token_info": {
                        "uid": "uid-secret",
                        "access_token": "access-token-secret",
                        "refresh_token": "refresh-token-secret",
                    },
                },
            }
        )

        result = await async_get_config_entry_diagnostics(hass, entry)
        rendered = repr(result)

        self.assertEqual(result[CONF_QR_AUTH], "**REDACTED**")
        for secret in (
            "user-code-secret",
            "terminal-secret",
            "secret-endpoint.invalid",
            "access-token-secret",
            "refresh-token-secret",
        ):
            self.assertNotIn(secret, rendered)


if __name__ == "__main__":
    unittest.main()
