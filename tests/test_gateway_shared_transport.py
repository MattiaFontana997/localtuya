"""Regression tests for shared Tuya gateway child transport."""

from __future__ import annotations

import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.localtuya import gateway_transport


class FakeParent:
    """Small pytuya-compatible physical gateway interface."""

    def __init__(self):
        self.id = "gateway-1"
        self.cid = None
        self.gateway_id = None
        self.version = 3.4
        self.dev_type = "v3.4"
        self.dps_cache = {}
        self.dps_to_request = {}
        self.transport = MagicMock()
        self.dispatcher = SimpleNamespace(listener=None)
        self.close = AsyncMock()
        self.status_calls = []
        self.set_calls = []

    async def status(self):
        self.status_calls.append((self.id, self.cid, self.gateway_id))
        self.dps_cache["1"] = self.cid
        await asyncio.sleep(0)
        return dict(self.dps_cache)

    async def set_dp(self, value, dp_index):
        self.set_calls.append((self.id, self.cid, self.gateway_id, dp_index, value))
        self.dps_cache[str(dp_index)] = value
        await asyncio.sleep(0)
        return {"dps": {str(dp_index): value}}

    async def set_dps(self, dps):
        for dp, value in dps.items():
            await self.set_dp(value, dp)
        return {"dps": dict(dps)}

    async def heartbeat(self):
        return None

    async def reset(self, dpIds=None):
        return True

    async def update_dps(self, dps=None):
        return True

    async def detect_available_dps(self):
        return await self.status()

    def _decode_payload(self, payload):
        return json.loads(payload.decode())


class FakeListener:
    def __init__(self):
        self.statuses = []
        self.disconnects = 0

    def status_updated(self, status):
        self.statuses.append(status)

    def disconnected(self):
        self.disconnects += 1


class SharedGatewayTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.parent = FakeParent()
        self.connect = AsyncMock(return_value=self.parent)
        self.hass = SimpleNamespace(data={})
        self.patch = patch.object(gateway_transport.pytuya, "connect", self.connect)
        self.patch.start()

    async def asyncTearDown(self):
        self.patch.stop()

    async def _acquire(self, device_id, cid, listener):
        return await gateway_transport.async_acquire_gateway_child(
            self.hass,
            host="192.168.1.80",
            gateway_id="gateway-1",
            local_key="0123456789abcdef",
            protocol_version=3.4,
            enable_debug=False,
            device_id=device_id,
            cid=cid,
            listener=listener,
        )

    async def test_multiple_children_share_one_physical_connection(self):
        first_listener = FakeListener()
        second_listener = FakeListener()
        first = await self._acquire("child-1", "cid-1", first_listener)
        second = await self._acquire("child-2", "cid-2", second_listener)

        self.connect.assert_awaited_once()
        self.assertIs(first._shared, second._shared)

        await first.status()
        await second.status()
        self.assertEqual(
            self.parent.status_calls,
            [
                ("child-1", "cid-1", "gateway-1"),
                ("child-2", "cid-2", "gateway-1"),
            ],
        )
        self.assertEqual(first.dps_cache["1"], "cid-1")
        self.assertEqual(second.dps_cache["1"], "cid-2")

    async def test_child_commands_are_serialized_and_scoped(self):
        first = await self._acquire("child-1", "cid-1", FakeListener())
        second = await self._acquire("child-2", "cid-2", FakeListener())

        await asyncio.gather(first.set_dp(True, 20), second.set_dp(False, 21))
        self.assertEqual(len(self.parent.set_calls), 2)
        self.assertEqual(
            {(call[0], call[1], call[2]) for call in self.parent.set_calls},
            {
                ("child-1", "cid-1", "gateway-1"),
                ("child-2", "cid-2", "gateway-1"),
            },
        )

    async def test_unsolicited_status_routes_only_to_matching_cid(self):
        first_listener = FakeListener()
        second_listener = FakeListener()
        first = await self._acquire("child-1", "cid-1", first_listener)
        await self._acquire("child-2", "cid-2", second_listener)

        message = SimpleNamespace(
            seqno=5,
            payload=json.dumps(
                {"cid": "cid-1", "dps": {"20": True}}
            ).encode(),
        )
        first._shared._status_message(message)

        self.assertEqual(first_listener.statuses, [{"20": True}])
        self.assertEqual(second_listener.statuses, [])

    async def test_physical_connection_closes_only_after_last_child(self):
        first = await self._acquire("child-1", "cid-1", FakeListener())
        second = await self._acquire("child-2", "cid-2", FakeListener())

        await first.close()
        self.parent.close.assert_not_awaited()
        await second.close()
        self.parent.close.assert_awaited_once()

    async def test_parent_disconnect_notifies_all_children(self):
        first_listener = FakeListener()
        second_listener = FakeListener()
        first = await self._acquire("child-1", "cid-1", first_listener)
        await self._acquire("child-2", "cid-2", second_listener)

        first._shared.parent_disconnected()
        self.assertEqual(first_listener.disconnects, 1)
        self.assertEqual(second_listener.disconnects, 1)

    async def test_dead_transport_is_replaced_on_next_acquire(self):
        first = await self._acquire("child-1", "cid-1", FakeListener())
        first_shared = first._shared
        second_parent = FakeParent()
        self.connect.side_effect = [second_parent]

        first_shared.parent_disconnected()
        second = await self._acquire("child-2", "cid-2", FakeListener())

        self.assertIsNot(second._shared, first_shared)
        self.assertIs(second._shared.parent, second_parent)
        self.assertEqual(self.connect.await_count, 2)
        self.parent.close.assert_awaited_once()

    async def test_heartbeat_failure_invalidates_and_notifies_children(self):
        first_listener = FakeListener()
        second_listener = FakeListener()
        first = await self._acquire("child-1", "cid-1", first_listener)
        await self._acquire("child-2", "cid-2", second_listener)
        self.parent.heartbeat = AsyncMock(side_effect=TimeoutError())

        await first._shared._heartbeat_loop()

        self.assertFalse(first._shared.alive)
        self.assertEqual(first_listener.disconnects, 1)
        self.assertEqual(second_listener.disconnects, 1)
        self.parent.transport.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
