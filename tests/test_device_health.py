"""Tests for the privacy-safe LocalTuya device preflight health model."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from custom_components.localtuya.device_health import (
    DeviceHealthAction,
    DeviceHealthFailure,
    DeviceHealthStage,
    ProtocolProbeOutcome,
    async_run_device_preflight,
)


_PROTOCOLS = ("3.5", "3.4", "3.3", "3.2", "3.1")


class FakeDecodeError(Exception):
    """Stand-in for a protocol/authentication decode failure."""


class DeviceHealthTests(unittest.IsolatedAsyncioTestCase):
    """Validate structured, privacy-safe preflight classification."""

    async def test_success_stops_at_first_working_protocol(self):
        probe = AsyncMock(return_value={"1": True, "20": 42})

        report = await async_run_device_preflight(
            requested_protocol="auto",
            supported_protocols=_PROTOCOLS,
            probe=probe,
        )

        self.assertTrue(report.ok)
        self.assertEqual(report.stage, DeviceHealthStage.READY)
        self.assertIsNone(report.failure)
        self.assertIsNone(report.recommended_action)
        self.assertIsNone(report.repair_key)
        self.assertEqual(report.resolved_protocol, "3.5")
        self.assertEqual(report.dp_ids, [1, 20])
        self.assertEqual(len(report.attempts), 1)
        self.assertEqual(
            report.attempts[0].outcome,
            ProtocolProbeOutcome.SUCCESS,
        )
        probe.assert_awaited_once_with("3.5")

    async def test_all_network_failures_are_host_unreachable(self):
        probe = AsyncMock(side_effect=TimeoutError("private detail"))

        report = await async_run_device_preflight(
            requested_protocol="auto",
            supported_protocols=_PROTOCOLS,
            probe=probe,
        )

        self.assertFalse(report.ok)
        self.assertEqual(report.stage, DeviceHealthStage.LAN)
        self.assertEqual(
            report.failure,
            DeviceHealthFailure.HOST_UNREACHABLE,
        )
        self.assertEqual(
            report.recommended_action,
            DeviceHealthAction.REDISCOVER_HOST,
        )
        self.assertEqual(
            report.repair_key,
            "device_health_rediscover_host",
        )
        self.assertEqual(len(report.attempts), len(_PROTOCOLS))
        self.assertTrue(
            all(
                attempt.outcome is ProtocolProbeOutcome.HOST_UNREACHABLE
                for attempt in report.attempts
            )
        )

    async def test_decode_failures_are_auth_or_protocol(self):
        probe = AsyncMock(
            side_effect=FakeDecodeError("local-secret must never escape")
        )

        report = await async_run_device_preflight(
            requested_protocol="auto",
            supported_protocols=_PROTOCOLS,
            probe=probe,
            auth_or_protocol_error_types=(FakeDecodeError,),
        )

        self.assertEqual(report.stage, DeviceHealthStage.PROTOCOL)
        self.assertEqual(
            report.failure,
            DeviceHealthFailure.AUTH_OR_PROTOCOL,
        )
        self.assertEqual(
            report.recommended_action,
            DeviceHealthAction.VERIFY_CREDENTIALS_OR_PROTOCOL,
        )
        self.assertEqual(
            {attempt.error_type for attempt in report.attempts},
            {"FakeDecodeError"},
        )

    async def test_connected_without_dps_is_classified_as_empty_dps(self):
        probe = AsyncMock(return_value={})

        report = await async_run_device_preflight(
            requested_protocol="auto",
            supported_protocols=_PROTOCOLS,
            probe=probe,
        )

        self.assertEqual(report.stage, DeviceHealthStage.DATAPOINTS)
        self.assertEqual(report.failure, DeviceHealthFailure.EMPTY_DPS)
        self.assertEqual(
            report.recommended_action,
            DeviceHealthAction.REVIEW_DATAPOINTS,
        )
        self.assertEqual(len(report.attempts), len(_PROTOCOLS))
        self.assertTrue(
            all(
                attempt.outcome is ProtocolProbeOutcome.NO_DPS
                for attempt in report.attempts
            )
        )

    async def test_invalid_explicit_protocol_fails_before_probe(self):
        probe = AsyncMock()

        report = await async_run_device_preflight(
            requested_protocol="9.9",
            supported_protocols=_PROTOCOLS,
            probe=probe,
        )

        self.assertEqual(report.stage, DeviceHealthStage.CONFIGURATION)
        self.assertEqual(
            report.failure,
            DeviceHealthFailure.INVALID_CONFIGURATION,
        )
        self.assertEqual(
            report.recommended_action,
            DeviceHealthAction.REVIEW_CONFIGURATION,
        )
        probe.assert_not_awaited()

    async def test_safe_diagnostics_do_not_expose_raw_values_or_secrets(self):
        secret = "super-secret-local-key"
        device_id = "private-device-id"
        host = "192.168.50.77"
        probe = AsyncMock(return_value={"1": secret, "2": device_id, "3": host})

        report = await async_run_device_preflight(
            requested_protocol="3.5",
            supported_protocols=_PROTOCOLS,
            probe=probe,
        )
        exported = report.as_dict()
        serialized = repr(exported)

        self.assertEqual(exported["dp_ids"], [1, 2, 3])
        self.assertEqual(exported["dps_count"], 3)
        self.assertIsNone(exported["recommended_action"])
        self.assertIsNone(exported["repair_key"])
        self.assertNotIn(secret, serialized)
        self.assertNotIn(device_id, serialized)
        self.assertNotIn(host, serialized)
        self.assertNotIn("detected_dps", exported)

    async def test_exception_message_is_not_exported(self):
        secret_message = "local_key=do-not-leak-this"
        probe = AsyncMock(side_effect=RuntimeError(secret_message))

        report = await async_run_device_preflight(
            requested_protocol="3.5",
            supported_protocols=_PROTOCOLS,
            probe=probe,
        )
        exported = report.as_dict()

        self.assertEqual(report.failure, DeviceHealthFailure.PROBE_ERROR)
        self.assertEqual(report.recommended_action, DeviceHealthAction.RETRY)
        self.assertEqual(exported["recommended_action"], "retry")
        self.assertEqual(exported["attempts"][0]["error_type"], "RuntimeError")
        self.assertNotIn(secret_message, repr(exported))

    async def test_every_failure_has_stable_repair_guidance(self):
        expected = {
            DeviceHealthFailure.INVALID_CONFIGURATION:
                DeviceHealthAction.REVIEW_CONFIGURATION,
            DeviceHealthFailure.HOST_UNREACHABLE:
                DeviceHealthAction.REDISCOVER_HOST,
            DeviceHealthFailure.AUTH_OR_PROTOCOL:
                DeviceHealthAction.VERIFY_CREDENTIALS_OR_PROTOCOL,
            DeviceHealthFailure.PROTOCOL_NOT_DETECTED:
                DeviceHealthAction.SELECT_PROTOCOL,
            DeviceHealthFailure.EMPTY_DPS:
                DeviceHealthAction.REVIEW_DATAPOINTS,
            DeviceHealthFailure.PROBE_ERROR:
                DeviceHealthAction.RETRY,
        }

        from custom_components.localtuya.device_health import DeviceHealthReport

        for failure, action in expected.items():
            report = DeviceHealthReport(
                requested_protocol="auto",
                stage=DeviceHealthStage.PROTOCOL,
                failure=failure,
            )
            self.assertEqual(report.recommended_action, action)
            self.assertEqual(
                report.repair_key,
                f"device_health_{action.value}",
            )


if __name__ == "__main__":
    unittest.main()
