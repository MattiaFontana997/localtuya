"""Tests for TinyTuya-style targeted Device ID discovery."""

import unittest
from unittest.mock import patch

from custom_components.localtuya.discovery import find_device


class _FakeDiscovery:
    instances = []
    emit_at_request = 3

    def __init__(self, callback=None, *, hass=None):
        self.callback = callback
        self.hass = hass
        self.devices = {}
        self.requests = 0
        self.closed = False
        type(self).instances.append(self)

    async def start(self):
        # Real TuyaDiscovery.start() sends the initial REQ_DEVINFO request.
        await self.async_request_discovery()

    async def async_request_discovery(self):
        self.requests += 1

        # An unrelated Tuya device may answer first; targeted discovery must
        # keep listening for the requested Device ID rather than returning it.
        if self.requests == 1:
            other = {
                "gwId": "other-device",
                "ip": "192.168.1.43",
                "version": "3.5",
            }
            self.devices[other["gwId"]] = other
            if self.callback is not None:
                self.callback(other)

        if self.emit_at_request and self.requests == self.emit_at_request:
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
        _FakeDiscovery.emit_at_request = 3

    async def test_rebroadcasts_until_target_and_exits_early(self):
        """A slow target can answer after multiple REQ_DEVINFO broadcasts."""
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
        self.assertEqual(result["gwId"], "wanted-device")
        instance = _FakeDiscovery.instances[-1]
        self.assertEqual(instance.requests, 3)
        self.assertTrue(instance.closed)

    async def test_timeout_returns_none_and_closes_listener(self):
        """A missing Device ID never falls back to an unrelated responder."""
        _FakeDiscovery.emit_at_request = 0
        with patch(
            "custom_components.localtuya.discovery.TuyaDiscovery",
            _FakeDiscovery,
        ):
            # Keep this bounded but leave enough scheduling margin for several
            # rebroadcast cycles on shared GitHub runners. Production timing is
            # 18 seconds with a 6-second interval; this only scales it down.
            result = await find_device(
                "missing-device",
                timeout=0.25,
                rebroadcast_interval=0.03,
                hass=object(),
            )

        self.assertIsNone(result)
        instance = _FakeDiscovery.instances[-1]
        self.assertGreaterEqual(instance.requests, 3)
        self.assertTrue(instance.closed)


if __name__ == "__main__":
    unittest.main()
