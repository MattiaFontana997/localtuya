"""Tests for TinyTuya-style targeted Device ID discovery."""

import unittest
from unittest.mock import patch

from custom_components.localtuya.discovery import find_device


class _FakeDiscovery:
    instances = []
    emit_on_rebroadcast = True

    def __init__(self, callback=None, *, hass=None):
        self.callback = callback
        self.hass = hass
        self.devices = {}
        self.requests = 0
        self.closed = False
        type(self).instances.append(self)

    async def start(self):
        return None

    async def async_request_discovery(self):
        self.requests += 1
        if self.emit_on_rebroadcast and self.requests == 1:
            payload = {
                "gwId": "wanted-device",
                "ip": "192.168.1.44",
                "version": "3.5",
            }
            self.devices[payload["gwId"]] = payload
            if self.callback is not None:
                self.callback(payload)
        return True

    def close(self):
        self.closed = True


class TargetedDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        _FakeDiscovery.instances = []
        _FakeDiscovery.emit_on_rebroadcast = True

    async def test_rebroadcast_finds_target_and_exits_early(self):
        with patch(
            "custom_components.localtuya.discovery.TuyaDiscovery",
            _FakeDiscovery,
        ):
            result = await find_device(
                "wanted-device",
                timeout=0.5,
                rebroadcast_interval=0.02,
                hass=object(),
            )

        self.assertEqual(result["ip"], "192.168.1.44")
        instance = _FakeDiscovery.instances[-1]
        self.assertEqual(instance.requests, 1)
        self.assertTrue(instance.closed)

    async def test_timeout_returns_none_and_closes_listener(self):
        _FakeDiscovery.emit_on_rebroadcast = False
        with patch(
            "custom_components.localtuya.discovery.TuyaDiscovery",
            _FakeDiscovery,
        ):
            result = await find_device(
                "missing-device",
                timeout=0.06,
                rebroadcast_interval=0.02,
                hass=object(),
            )

        self.assertIsNone(result)
        instance = _FakeDiscovery.instances[-1]
        self.assertGreaterEqual(instance.requests, 2)
        self.assertTrue(instance.closed)


if __name__ == "__main__":
    unittest.main()
