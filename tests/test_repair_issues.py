"""Tests for LocalTuya Home Assistant repair issue helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from custom_components.localtuya.host_recovery import HostRecoveryOutcome
from custom_components.localtuya.device_health import (
    DeviceHealthFailure,
    DeviceHealthReport,
    DeviceHealthStage,
)
from custom_components.localtuya.repair_issues import (
    async_clear_host_recovery_issue,
    async_sync_device_health_issue,
    async_sync_host_recovery_issue,
    device_health_issue_id,
    host_recovery_issue_id,
)


class RepairIssueTests(unittest.TestCase):
    """Verify repair issue lifecycle and privacy boundaries."""

    def test_issue_id_is_stable_and_does_not_expose_device_id(self):
        device_id = "bf-private-tuya-device-id"

        first = host_recovery_issue_id(device_id)
        second = host_recovery_issue_id(device_id)

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("host_recovery_"))
        self.assertNotIn(device_id, first)

    @patch("custom_components.localtuya.repair_issues.ir.async_delete_issue")
    @patch("custom_components.localtuya.repair_issues.ir.async_create_issue")
    def test_validation_failure_creates_privacy_safe_warning(
        self,
        create_issue,
        delete_issue,
    ):
        hass = object()
        device_id = "private-device-id"

        async_sync_host_recovery_issue(
            hass,
            device_id=device_id,
            device_name="Kitchen light",
            outcome=HostRecoveryOutcome.VALIDATION_FAILED,
        )

        delete_issue.assert_not_called()
        create_issue.assert_called_once()
        args = create_issue.call_args.args
        kwargs = create_issue.call_args.kwargs

        self.assertIs(args[0], hass)
        self.assertNotIn(device_id, args[2])
        self.assertTrue(kwargs["is_fixable"])
        self.assertTrue(kwargs["is_persistent"])
        self.assertEqual(kwargs["translation_key"], "host_recovery_failed")
        self.assertEqual(
            kwargs["translation_placeholders"],
            {"device_name": "Kitchen light"},
        )

        serialized = repr(create_issue.call_args)
        self.assertNotIn(device_id, serialized)
        self.assertNotIn("TimeoutError", serialized)

    @patch("custom_components.localtuya.repair_issues.ir.async_delete_issue")
    @patch("custom_components.localtuya.repair_issues.ir.async_create_issue")
    def test_recovered_outcomes_clear_existing_issue(
        self,
        create_issue,
        delete_issue,
    ):
        hass = object()

        for outcome in (
            HostRecoveryOutcome.UNCHANGED,
            HostRecoveryOutcome.UPDATED,
            HostRecoveryOutcome.METADATA_UPDATED,
        ):
            with self.subTest(outcome=outcome):
                delete_issue.reset_mock()
                async_sync_host_recovery_issue(
                    hass,
                    device_id="device-1",
                    device_name="Device",
                    outcome=outcome,
                )
                delete_issue.assert_called_once()

        create_issue.assert_not_called()

    @patch("custom_components.localtuya.repair_issues.ir.async_delete_issue")
    @patch("custom_components.localtuya.repair_issues.ir.async_create_issue")
    def test_non_actionable_outcomes_do_not_create_or_clear_issue(
        self,
        create_issue,
        delete_issue,
    ):
        hass = object()

        for outcome in (
            HostRecoveryOutcome.INVALID_ADDRESS,
            HostRecoveryOutcome.DEVICE_NOT_CONFIGURED,
            HostRecoveryOutcome.STALE,
        ):
            with self.subTest(outcome=outcome):
                async_sync_host_recovery_issue(
                    hass,
                    device_id="device-1",
                    device_name="Device",
                    outcome=outcome,
                )

        create_issue.assert_not_called()
        delete_issue.assert_not_called()

    @patch("custom_components.localtuya.repair_issues.ir.async_delete_issue")
    @patch("custom_components.localtuya.repair_issues.ir.async_create_issue")
    def test_health_failure_creates_specific_private_fixable_issue(
        self, create_issue, delete_issue
    ):
        hass = object()
        device_id = "private-health-device"
        report = DeviceHealthReport(
            requested_protocol="auto",
            stage=DeviceHealthStage.PROTOCOL,
            failure=DeviceHealthFailure.AUTH_OR_PROTOCOL,
        )
        async_sync_device_health_issue(
            hass, device_id=device_id, device_name="Bedroom lamp", report=report
        )
        self.assertTrue(delete_issue.called)
        create_issue.assert_called_once()
        args = create_issue.call_args.args
        kwargs = create_issue.call_args.kwargs
        self.assertEqual(args[2], device_health_issue_id(device_id, "auth_or_protocol"))
        self.assertNotIn(device_id, args[2])
        self.assertTrue(kwargs["is_fixable"])
        self.assertEqual(kwargs["translation_key"], "device_health_auth_or_protocol")

    @patch("custom_components.localtuya.repair_issues.ir.async_delete_issue")
    def test_explicit_clear_uses_hashed_issue_id(self, delete_issue):
        hass = object()
        device_id = "private-device-id"

        async_clear_host_recovery_issue(hass, device_id)

        delete_issue.assert_called_once()
        args = delete_issue.call_args.args
        self.assertIs(args[0], hass)
        self.assertNotIn(device_id, args[2])


if __name__ == "__main__":
    unittest.main()
