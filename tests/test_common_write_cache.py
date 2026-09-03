"""Tests for LocalTuya write-through DPS cache."""

import unittest
from unittest.mock import Mock

from custom_components.localtuya.common import (
    TuyaDevice,
)


class FakeInterface:
    """Minimal Tuya interface used by write-cache tests."""

    def __init__(self):
        self.calls = []
        self.dps_cache = {
            "16": 205,
            "32": 205,
        }

    async def set_dp(
        self,
        value,
        dp_index,
    ):
        self.calls.append(
            (
                "set_dp",
                dp_index,
                value,
            )
        )

    async def set_dps(
        self,
        states,
    ):
        self.calls.append(
            (
                "set_dps",
                dict(states),
            )
        )


class WriteCacheTests(
    unittest.IsolatedAsyncioTestCase
):
    """Verify successful writes update HA's local DPS cache."""

    @staticmethod
    def _device():
        device = object.__new__(
            TuyaDevice
        )

        device._interface = (
            FakeInterface()
        )

        device._status = {
            "16": 205,
            "32": 205,
        }

        device._dispatch_status = Mock()

        return device

    async def test_set_dp_updates_cached_status(self):
        device = self._device()

        await device.set_dp(
            220,
            32,
        )

        self.assertEqual(
            device._status["32"],
            220,
        )

        self.assertEqual(
            device._interface.dps_cache[
                "32"
            ],
            220,
        )

        device._dispatch_status.assert_called_once()

    async def test_set_dps_updates_cached_status(self):
        device = self._device()

        await device.set_dps(
            {
                32: 215,
                33: 3,
            }
        )

        self.assertEqual(
            device._status["32"],
            215,
        )

        self.assertEqual(
            device._status["33"],
            3,
        )

        device._dispatch_status.assert_called_once()


if __name__ == "__main__":
    unittest.main()
