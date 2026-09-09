"""Tests for the reusable LocalTuya LAN protocol probe."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_DEVICE_ID, CONF_HOST

from custom_components.localtuya import device_probe
from custom_components.localtuya.const import (
    CONF_ENABLE_DEBUG,
    CONF_LOCAL_KEY,
)


class DeviceProbeTests(unittest.IsolatedAsyncioTestCase):
    """Protect gateway routing and bounded transient-connect retries."""

    @staticmethod
    def _child_data() -> dict:
        return {
            CONF_HOST: "192.168.1.50",
            CONF_DEVICE_ID: "child-device-1",
            CONF_LOCAL_KEY: "0123456789abcdef",
            CONF_ENABLE_DEBUG: False,
            "node_id": "node-123",
            "gateway_id": "gateway-device-1",
        }

    async def test_child_routing_metadata_is_forwarded_to_pytuya(self):
        interface = unittest.mock.MagicMock()
        interface.detect_available_dps = AsyncMock(
            return_value={"1": True, "20": 42}
        )
        interface.close = AsyncMock()
        connect = AsyncMock(return_value=interface)

        with patch.object(device_probe.pytuya, "connect", connect):
            result = await device_probe._async_probe_protocol(
                self._child_data(),
                "3.4",
                [],
            )

        self.assertEqual(result, {"1": True, "20": 42})
        connect.assert_awaited_once_with(
            "192.168.1.50",
            "child-device-1",
            "0123456789abcdef",
            3.4,
            False,
            cid="node-123",
            gateway_id="gateway-device-1",
        )
        interface.detect_available_dps.assert_awaited_once_with()
        interface.close.assert_awaited_once_with()

    async def test_transient_connect_failure_is_retried_once(self):
        interface = unittest.mock.MagicMock()
        interface.detect_available_dps = AsyncMock(return_value={"1": True})
        interface.close = AsyncMock()
        connect = AsyncMock(
            side_effect=[
                ConnectionResetError("transient reset"),
                interface,
            ]
        )
        sleep = AsyncMock()

        with (
            patch.object(device_probe.pytuya, "connect", connect),
            patch.object(device_probe.asyncio, "sleep", sleep),
        ):
            result = await device_probe._async_probe_protocol(
                self._child_data(),
                "3.5",
                [],
            )

        self.assertEqual(result, {"1": True})
        self.assertEqual(connect.await_count, 2)
        sleep.assert_awaited_once_with(0.35)
        interface.detect_available_dps.assert_awaited_once_with()
        interface.close.assert_awaited_once_with()

    async def test_second_connect_failure_is_propagated(self):
        connect = AsyncMock(
            side_effect=[
                OSError("first failure"),
                OSError("second failure"),
            ]
        )
        sleep = AsyncMock()

        with (
            patch.object(device_probe.pytuya, "connect", connect),
            patch.object(device_probe.asyncio, "sleep", sleep),
        ):
            with self.assertRaises(OSError):
                await device_probe._async_probe_protocol(
                    self._child_data(),
                    "3.4",
                    [],
                )

        self.assertEqual(connect.await_count, 2)
        sleep.assert_awaited_once_with(0.35)


if __name__ == "__main__":
    unittest.main()
