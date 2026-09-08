"""Tests for validated automatic LocalTuya host recovery."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from homeassistant.const import CONF_DEVICE_ID, CONF_DEVICES, CONF_HOST

from custom_components.localtuya.const import (
    ATTR_UPDATED_AT,
    CONF_LOCAL_KEY,
    CONF_PRODUCT_KEY,
    CONF_PROTOCOL_VERSION,
)
from custom_components.localtuya.host_recovery import (
    HostRecoveryOutcome,
    async_recover_discovered_host,
)


class FakeConfigEntries:
    """Minimal config-entry manager that applies updates immediately."""

    def __init__(self):
        self.updated = []

    def async_update_entry(self, entry, *, data):
        self.updated.append(data)
        entry.data = data


class HostRecoveryTests(unittest.IsolatedAsyncioTestCase):
    """Validate safe address recovery semantics."""

    def setUp(self):
        self.manager = FakeConfigEntries()
        self.hass = SimpleNamespace(config_entries=self.manager)
        self.entry = SimpleNamespace(
            data={
                CONF_DEVICES: {
                    "device-1": {
                        CONF_HOST: "192.168.1.20",
                        CONF_LOCAL_KEY: "private-local-key",
                        CONF_PROTOCOL_VERSION: "3.5",
                        CONF_PRODUCT_KEY: "product-old",
                    }
                }
            }
        )

    async def test_changed_host_is_validated_before_persisting(self):
        validator = AsyncMock(return_value=(["1 (value: True)"], "3.5"))

        result = await async_recover_discovered_host(
            self.hass,
            self.entry,
            "device-1",
            "192.168.1.44",
            validator=validator,
            product_key="product-new",
        )

        self.assertEqual(result.outcome, HostRecoveryOutcome.UPDATED)
        self.assertTrue(result.applied)
        self.assertEqual(
            self.entry.data[CONF_DEVICES]["device-1"][CONF_HOST],
            "192.168.1.44",
        )
        self.assertEqual(
            self.entry.data[CONF_DEVICES]["device-1"][CONF_PRODUCT_KEY],
            "product-new",
        )
        self.assertIn(ATTR_UPDATED_AT, self.entry.data)

        validator.assert_awaited_once()
        _, probe_data = validator.await_args.args
        self.assertEqual(probe_data[CONF_DEVICE_ID], "device-1")
        self.assertEqual(probe_data[CONF_HOST], "192.168.1.44")
        self.assertEqual(probe_data[CONF_LOCAL_KEY], "private-local-key")

    async def test_failed_validation_never_changes_host(self):
        secret = "local_key=must-not-leak"
        validator = AsyncMock(side_effect=TimeoutError(secret))

        result = await async_recover_discovered_host(
            self.hass,
            self.entry,
            "device-1",
            "192.168.1.55",
            validator=validator,
        )

        self.assertEqual(
            result.outcome,
            HostRecoveryOutcome.VALIDATION_FAILED,
        )
        self.assertEqual(result.validation_error_type, "TimeoutError")
        self.assertFalse(result.applied)
        self.assertEqual(
            self.entry.data[CONF_DEVICES]["device-1"][CONF_HOST],
            "192.168.1.20",
        )
        self.assertEqual(self.manager.updated, [])
        self.assertNotIn(secret, repr(result.as_dict()))
        self.assertNotIn("192.168.1.55", repr(result.as_dict()))
        self.assertNotIn("device-1", repr(result.as_dict()))

    async def test_slow_probe_cannot_overwrite_newer_host(self):
        async def validator(_hass, _probe_data):
            self.entry.data[CONF_DEVICES]["device-1"][CONF_HOST] = (
                "192.168.1.99"
            )
            return (["1 (value: True)"], "3.5")

        result = await async_recover_discovered_host(
            self.hass,
            self.entry,
            "device-1",
            "192.168.1.44",
            validator=validator,
        )

        self.assertEqual(result.outcome, HostRecoveryOutcome.STALE)
        self.assertFalse(result.applied)
        self.assertEqual(
            self.entry.data[CONF_DEVICES]["device-1"][CONF_HOST],
            "192.168.1.99",
        )
        self.assertEqual(self.manager.updated, [])

    async def test_same_host_skips_validation(self):
        validator = AsyncMock()

        result = await async_recover_discovered_host(
            self.hass,
            self.entry,
            "device-1",
            "192.168.1.20",
            validator=validator,
        )

        self.assertEqual(result.outcome, HostRecoveryOutcome.UNCHANGED)
        validator.assert_not_awaited()
        self.assertEqual(self.manager.updated, [])

    async def test_same_host_can_refresh_product_metadata_without_probe(self):
        validator = AsyncMock()

        result = await async_recover_discovered_host(
            self.hass,
            self.entry,
            "device-1",
            "192.168.1.20",
            validator=validator,
            product_key="product-new",
        )

        self.assertEqual(
            result.outcome,
            HostRecoveryOutcome.METADATA_UPDATED,
        )
        self.assertEqual(
            self.entry.data[CONF_DEVICES]["device-1"][CONF_PRODUCT_KEY],
            "product-new",
        )
        validator.assert_not_awaited()
        self.assertEqual(len(self.manager.updated), 1)

    async def test_invalid_or_unknown_candidate_fails_closed(self):
        validator = AsyncMock()

        invalid = await async_recover_discovered_host(
            self.hass,
            self.entry,
            "device-1",
            "   ",
            validator=validator,
        )
        unknown = await async_recover_discovered_host(
            self.hass,
            self.entry,
            "missing-device",
            "192.168.1.44",
            validator=validator,
        )

        self.assertEqual(
            invalid.outcome,
            HostRecoveryOutcome.INVALID_ADDRESS,
        )
        self.assertEqual(
            unknown.outcome,
            HostRecoveryOutcome.DEVICE_NOT_CONFIGURED,
        )
        validator.assert_not_awaited()
        self.assertEqual(self.manager.updated, [])


if __name__ == "__main__":
    unittest.main()
