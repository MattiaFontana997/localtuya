"""Integration tests for config-flow device health preflight handling."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from custom_components.localtuya import config_flow
from custom_components.localtuya.device_health import (
    DeviceHealthFailure,
    DeviceHealthStage,
    ProtocolProbeOutcome,
)


class TestConfigFlowDeviceHealth(unittest.IsolatedAsyncioTestCase):
    """Verify the structured preflight without changing validate_input API."""

    def _data(self, protocol="auto", **extra):
        data = {
            config_flow.CONF_HOST: "10.0.21.142",
            config_flow.CONF_DEVICE_ID: "test-device",
            config_flow.CONF_LOCAL_KEY: "0123456789abcdef",
            config_flow.CONF_PROTOCOL_VERSION: protocol,
            config_flow.CONF_ENABLE_DEBUG: False,
        }
        data.update(extra)
        return data

    async def test_preflight_records_attempts_until_protocol_succeeds(self):
        probe = AsyncMock(
            side_effect=[
                TimeoutError("must not be exported"),
                {"1": True, "20": 42},
            ]
        )

        with patch.object(
            config_flow,
            "_async_probe_protocol",
            probe,
        ):
            report = await config_flow.async_device_preflight(
                None,
                self._data(),
            )

        self.assertTrue(report.ok)
        self.assertEqual(report.stage, DeviceHealthStage.READY)
        self.assertEqual(report.resolved_protocol, "3.4")
        self.assertEqual(report.dp_ids, [1, 20])
        self.assertEqual(len(report.attempts), 2)
        self.assertEqual(
            report.attempts[0].outcome,
            ProtocolProbeOutcome.HOST_UNREACHABLE,
        )
        self.assertEqual(
            report.attempts[1].outcome,
            ProtocolProbeOutcome.SUCCESS,
        )
        self.assertNotIn("must not be exported", repr(report.as_dict()))

    async def test_auto_all_network_failures_remains_cannot_connect(self):
        probe = AsyncMock(side_effect=TimeoutError("offline"))

        with patch.object(
            config_flow,
            "_async_probe_protocol",
            probe,
        ):
            with self.assertRaises(config_flow.CannotConnect):
                await config_flow.validate_input(
                    None,
                    self._data(),
                )

        self.assertEqual(
            probe.await_count,
            len(config_flow.SUPPORTED_PROTOCOL_VERSIONS),
        )

    async def test_auto_connected_without_dps_reports_empty_dps(self):
        probe = AsyncMock(return_value={})

        with patch.object(
            config_flow,
            "_async_probe_protocol",
            probe,
        ):
            report = await config_flow.async_device_preflight(
                None,
                self._data(),
            )

            self.assertEqual(
                report.failure,
                DeviceHealthFailure.EMPTY_DPS,
            )
            self.assertEqual(
                report.stage,
                DeviceHealthStage.DATAPOINTS,
            )

            with self.assertRaises(config_flow.EmptyDpsList):
                await config_flow.validate_input(
                    None,
                    self._data(),
                )

    async def test_explicit_auth_failure_remains_invalid_auth(self):
        probe = AsyncMock(side_effect=ValueError("wrong key detail"))

        with patch.object(
            config_flow,
            "_async_probe_protocol",
            probe,
        ):
            with self.assertRaises(config_flow.InvalidAuth):
                await config_flow.validate_input(
                    None,
                    self._data("3.5"),
                )

        probe.assert_awaited_once()

    async def test_explicit_protocol_keeps_manual_dps_escape_hatch(self):
        probe = AsyncMock(return_value={})

        with patch.object(
            config_flow,
            "_async_probe_protocol",
            probe,
        ):
            dps, protocol = await config_flow.validate_input(
                None,
                self._data(
                    "3.5",
                    **{config_flow.CONF_MANUAL_DPS: "1, 20"},
                ),
            )

        self.assertEqual(protocol, "3.5")
        self.assertEqual(
            dps,
            ["1 (value: -1)", "20 (value: -1)"],
        )

    async def test_invalid_reset_dps_returns_safe_configuration_failure(self):
        probe = AsyncMock()

        with patch.object(
            config_flow,
            "_async_probe_protocol",
            probe,
        ):
            report = await config_flow.async_device_preflight(
                None,
                self._data(
                    **{config_flow.CONF_RESET_DPIDS: "1,not-a-number"},
                ),
            )

        self.assertFalse(report.ok)
        self.assertEqual(report.stage, DeviceHealthStage.CONFIGURATION)
        self.assertEqual(
            report.failure,
            DeviceHealthFailure.INVALID_CONFIGURATION,
        )
        probe.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
