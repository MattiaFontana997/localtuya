"""Tests for privacy-safe LocalTuya runtime device health helpers."""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from custom_components.localtuya.const import DOMAIN, TUYA_DEVICES
from custom_components.localtuya.device_health import (
    DeviceHealthReport,
    DeviceHealthStage,
)
from custom_components.localtuya.health_runtime import (
    async_build_device_health_snapshot,
)
from custom_components.localtuya.health_service import (
    DeviceHealthTargetNotFound,
    async_check_configured_device_health,
)


class HealthRuntimeTests(unittest.IsolatedAsyncioTestCase):
    """Validate bounded health snapshots and configured-device lookup."""

    def setUp(self):
        self.device_id = "private-device-id"
        self.device_config = {
            "friendly_name": "Kitchen Plug",
            "host": "192.168.1.50",
            "local_key": "super-secret-local-key",
            "protocol_version": "3.5",
        }
        self.hass = SimpleNamespace(
            data={
                DOMAIN: {
                    TUYA_DEVICES: {
                        self.device_id: SimpleNamespace(
                            connected=True,
                        )
                    }
                }
            }
        )

    async def test_snapshot_contains_only_safe_preflight_output(self):
        report = DeviceHealthReport(
            requested_protocol="3.5",
            resolved_protocol="3.5",
            stage=DeviceHealthStage.READY,
            detected_dps={
                "1": "raw-private-value",
                "20": True,
            },
        )

        with patch(
            "custom_components.localtuya.health_runtime.async_device_preflight",
            new=AsyncMock(return_value=report),
        ) as preflight:
            result = await async_build_device_health_snapshot(
                self.hass,
                self.device_id,
                self.device_config,
            )

        self.assertTrue(result["runtime_present"])
        self.assertTrue(result["runtime_connected"])
        self.assertTrue(result["preflight"]["ok"])
        self.assertEqual(result["preflight"]["dp_ids"], [1, 20])
        self.assertNotIn("detected_dps", result["preflight"])

        rendered = repr(result)
        for private_value in (
            self.device_id,
            "192.168.1.50",
            "super-secret-local-key",
            "raw-private-value",
        ):
            self.assertNotIn(private_value, rendered)

        probe_data = preflight.await_args.args[1]
        self.assertEqual(probe_data["device_id"], self.device_id)
        self.assertEqual(probe_data["local_key"], "super-secret-local-key")
        self.assertIsNot(probe_data, self.device_config)

    async def test_probe_exception_exposes_only_exception_class(self):
        private_message = (
            "host=192.168.1.50 local_key=super-secret-local-key"
        )

        with patch(
            "custom_components.localtuya.health_runtime.async_device_preflight",
            new=AsyncMock(side_effect=RuntimeError(private_message)),
        ):
            result = await async_build_device_health_snapshot(
                self.hass,
                self.device_id,
                self.device_config,
            )

        self.assertIsNone(result["preflight"])
        self.assertEqual(result["probe_error_type"], "RuntimeError")
        self.assertNotIn(private_message, repr(result))

    async def test_probe_timeout_is_bounded_and_privacy_safe(self):
        async def slow_preflight(*_args, **_kwargs):
            await asyncio.sleep(1)

        with patch(
            "custom_components.localtuya.health_runtime.async_device_preflight",
            side_effect=slow_preflight,
        ):
            result = await async_build_device_health_snapshot(
                self.hass,
                self.device_id,
                self.device_config,
                timeout=0.001,
            )

        self.assertIsNone(result["preflight"])
        self.assertEqual(result["probe_error_type"], "TimeoutError")

    async def test_missing_runtime_device_is_reported_without_identifier(self):
        hass = SimpleNamespace(
            data={DOMAIN: {TUYA_DEVICES: {}}}
        )
        report = DeviceHealthReport(
            requested_protocol="3.5",
            resolved_protocol="3.5",
            stage=DeviceHealthStage.READY,
            detected_dps={"1": True},
        )

        with patch(
            "custom_components.localtuya.health_runtime.async_device_preflight",
            new=AsyncMock(return_value=report),
        ):
            result = await async_build_device_health_snapshot(
                hass,
                self.device_id,
                self.device_config,
            )

        self.assertFalse(result["runtime_present"])
        self.assertIsNone(result["runtime_connected"])
        self.assertNotIn(self.device_id, repr(result))

    async def test_configured_device_service_delegates_to_safe_snapshot(self):
        entry = SimpleNamespace(
            data={
                "devices": {
                    self.device_id: self.device_config,
                }
            }
        )
        expected = {
            "runtime_present": True,
            "runtime_connected": True,
            "preflight": {"ok": True},
        }

        with (
            patch(
                "custom_components.localtuya.health_service.async_config_entry_by_device_id",
                return_value=entry,
            ),
            patch(
                "custom_components.localtuya.health_service.async_build_device_health_snapshot",
                new=AsyncMock(return_value=expected),
            ) as snapshot,
        ):
            result = await async_check_configured_device_health(
                self.hass,
                self.device_id,
            )

        self.assertEqual(result, expected)
        snapshot.assert_awaited_once()
        passed_config = snapshot.await_args.args[2]
        self.assertEqual(passed_config, self.device_config)
        self.assertIsNot(passed_config, self.device_config)

    async def test_unknown_configured_device_is_rejected_without_echoing_id(self):
        with patch(
            "custom_components.localtuya.health_service.async_config_entry_by_device_id",
            return_value=None,
        ):
            with self.assertRaises(DeviceHealthTargetNotFound) as ctx:
                await async_check_configured_device_health(
                    self.hass,
                    self.device_id,
                )

        self.assertNotIn(self.device_id, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
