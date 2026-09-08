"""Tests for LocalTuya interactive Home Assistant repair flows."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.components.repairs import ConfirmRepairFlow
from homeassistant.const import CONF_DEVICES, CONF_HOST

from custom_components.localtuya.const import CONF_LOCAL_KEY, CONF_PROTOCOL_VERSION, DOMAIN
from custom_components.localtuya.host_recovery import HostRecoveryOutcome, HostRecoveryResult
from custom_components.localtuya.repair_issues import host_recovery_issue_id
from custom_components.localtuya.repairs import (
    HostRecoveryRepairFlow,
    _find_repair_target,
    _validation_error_key,
    async_create_fix_flow,
)


class FakeConfigEntries:
    """Small config-entry manager for repair-flow tests."""

    def __init__(self, entries):
        self._entries = list(entries)

    def async_entries(self, domain=None):
        if domain is not None and domain != DOMAIN:
            return []
        return list(self._entries)


class RepairsTests(unittest.IsolatedAsyncioTestCase):
    """Verify privacy-safe target resolution and validated host repair."""

    def setUp(self):
        self.device_id = "private-tuya-device-id"
        self.entry = SimpleNamespace(
            entry_id="entry-1",
            data={
                CONF_DEVICES: {
                    self.device_id: {
                        CONF_HOST: "192.168.1.20",
                        CONF_LOCAL_KEY: "private-key",
                        CONF_PROTOCOL_VERSION: "3.5",
                        "friendly_name": "Kitchen light",
                    }
                }
            },
        )
        self.hass = SimpleNamespace(
            config_entries=FakeConfigEntries([self.entry]),
            data={DOMAIN: {}},
        )

    def test_issue_id_resolves_only_in_memory(self):
        issue_id = host_recovery_issue_id(self.device_id)

        target = _find_repair_target(self.hass, issue_id)

        self.assertIsNotNone(target)
        self.assertIs(target.entry, self.entry)
        self.assertEqual(target.device_id, self.device_id)
        self.assertEqual(target.device_name, "Kitchen light")
        self.assertNotIn(self.device_id, issue_id)

    def test_unknown_issue_does_not_resolve(self):
        self.assertIsNone(
            _find_repair_target(self.hass, "host_recovery_deadbeefdeadbeef")
        )

    def test_validation_error_classification_is_stable(self):
        self.assertEqual(_validation_error_key("CannotConnect"), "cannot_connect")
        self.assertEqual(_validation_error_key("InvalidAuth"), "invalid_auth")
        self.assertEqual(_validation_error_key("EmptyDpsList"), "empty_dps")
        self.assertEqual(_validation_error_key("SomethingPrivate"), "unknown")

    async def test_create_fix_flow_for_known_hashed_issue(self):
        flow = await async_create_fix_flow(
            self.hass,
            host_recovery_issue_id(self.device_id),
            None,
        )

        self.assertIsInstance(flow, HostRecoveryRepairFlow)

    async def test_unknown_issue_uses_safe_fallback_flow(self):
        flow = await async_create_fix_flow(self.hass, "other_issue", None)

        self.assertIsInstance(flow, ConfirmRepairFlow)

    async def test_changed_host_is_applied_only_through_validated_recovery(self):
        target = _find_repair_target(
            self.hass,
            host_recovery_issue_id(self.device_id),
        )
        flow = HostRecoveryRepairFlow(target)
        flow.hass = self.hass

        with (
            patch(
                "custom_components.localtuya.repairs.async_recover_discovered_host",
                new=AsyncMock(
                    return_value=HostRecoveryResult(HostRecoveryOutcome.UPDATED)
                ),
            ) as recover,
            patch(
                "custom_components.localtuya.repairs.async_clear_host_recovery_issue"
            ) as clear_issue,
        ):
            error = await flow._async_apply_candidate("192.168.1.44")

        self.assertIsNone(error)
        recover.assert_awaited_once()
        self.assertEqual(recover.await_args.args[2], self.device_id)
        self.assertEqual(recover.await_args.args[3], "192.168.1.44")
        clear_issue.assert_called_once_with(self.hass, self.device_id)

    async def test_current_host_is_revalidated_before_issue_is_cleared(self):
        target = _find_repair_target(
            self.hass,
            host_recovery_issue_id(self.device_id),
        )
        flow = HostRecoveryRepairFlow(target)
        flow.hass = self.hass

        with (
            patch(
                "custom_components.localtuya.repairs.validate_input",
                new=AsyncMock(return_value=(["1 (value: True)"], "3.5")),
            ) as validator,
            patch(
                "custom_components.localtuya.repairs.async_clear_host_recovery_issue"
            ) as clear_issue,
        ):
            error = await flow._async_apply_candidate("192.168.1.20")

        self.assertIsNone(error)
        validator.assert_awaited_once()
        probe = validator.await_args.args[1]
        self.assertEqual(probe[CONF_HOST], "192.168.1.20")
        self.assertEqual(probe[CONF_LOCAL_KEY], "private-key")
        clear_issue.assert_called_once_with(self.hass, self.device_id)

    async def test_failed_changed_host_keeps_repair_open(self):
        target = _find_repair_target(
            self.hass,
            host_recovery_issue_id(self.device_id),
        )
        flow = HostRecoveryRepairFlow(target)
        flow.hass = self.hass

        with patch(
            "custom_components.localtuya.repairs.async_recover_discovered_host",
            new=AsyncMock(
                return_value=HostRecoveryResult(
                    HostRecoveryOutcome.VALIDATION_FAILED,
                    validation_error_type="InvalidAuth",
                )
            ),
        ):
            error = await flow._async_apply_candidate("192.168.1.99")

        self.assertEqual(error, "invalid_auth")


if __name__ == "__main__":
    unittest.main()
