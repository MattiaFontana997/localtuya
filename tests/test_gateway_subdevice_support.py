"""Regression tests for Tuya gateway child-device routing."""

from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import AsyncMock

from custom_components.localtuya import pytuya


class GatewaySubdeviceProtocolTests(unittest.IsolatedAsyncioTestCase):
    """Verify child addressing without requiring real Tuya hardware."""

    def _protocol(self, version: float) -> pytuya.TuyaProtocol:
        loop = asyncio.get_running_loop()
        connected = loop.create_future()
        return pytuya.TuyaProtocol(
            "child-device-id",
            "0123456789abcdef",
            version,
            False,
            connected,
            pytuya.EmptyListener(),
            cid="node-123",
            gateway_id="gateway-device-id",
        )

    def _direct_protocol(self, version: float) -> pytuya.TuyaProtocol:
        loop = asyncio.get_running_loop()
        connected = loop.create_future()
        return pytuya.TuyaProtocol(
            "direct-device-id",
            "0123456789abcdef",
            version,
            False,
            connected,
            pytuya.EmptyListener(),
        )

    async def test_v33_child_control_uses_gateway_child_payload(self):
        protocol = self._protocol(3.3)

        payload = protocol._generate_payload(
            pytuya.CONTROL,
            {"1": True},
        )
        body = json.loads(payload.payload.decode())

        self.assertEqual(body["cid"], "node-123")
        self.assertEqual(body["dps"], {"1": True})
        self.assertIn("t", body)
        self.assertNotIn("devId", body)
        self.assertNotIn("gwId", body)

    async def test_v33_child_query_uses_gateway_child_payload(self):
        protocol = self._protocol(3.3)

        payload = protocol._generate_payload(pytuya.DP_QUERY)
        body = json.loads(payload.payload.decode())

        self.assertEqual(body["cid"], "node-123")
        self.assertIn("t", body)
        self.assertNotIn("devId", body)
        self.assertNotIn("gwId", body)

    async def test_v35_child_control_preserves_nested_cid_and_dps(self):
        protocol = self._protocol(3.5)

        payload = protocol._generate_payload(
            pytuya.CONTROL,
            {"20": True},
        )
        body = json.loads(payload.payload.decode())

        self.assertEqual(body["cid"], "node-123")
        self.assertEqual(body["data"]["cid"], "node-123")
        self.assertEqual(body["data"]["ctype"], 0)
        self.assertEqual(body["data"]["dps"], {"20": True})

    async def test_v35_child_query_keeps_cid_top_level_only(self):
        protocol = self._protocol(3.5)

        payload = protocol._generate_payload(pytuya.DP_QUERY)
        body = json.loads(payload.payload.decode())

        self.assertEqual(body, {"cid": "node-123"})
        self.assertEqual(payload.cmd, pytuya.DP_QUERY_NEW)

    async def test_v35_child_heartbeat_does_not_invent_nested_data(self):
        protocol = self._protocol(3.5)

        payload = protocol._generate_payload(pytuya.HEART_BEAT)
        body = json.loads(payload.payload.decode())

        self.assertEqual(body["cid"], "node-123")
        self.assertEqual(body["gwId"], "gateway-device-id")
        self.assertNotIn("data", body)

    async def test_v35_direct_query_fallback_uses_explicit_data_dps(self):
        protocol = self._direct_protocol(3.5)
        protocol._v35_query_fallback = True

        payload = protocol._generate_payload(pytuya.DP_QUERY)
        body = json.loads(payload.payload.decode())

        self.assertEqual(body, {"data": {"dps": {}}})
        self.assertEqual(payload.cmd, pytuya.DP_QUERY_NEW)

    async def test_v35_data_unvalid_requests_query_shape_retry(self):
        protocol = self._direct_protocol(3.5)

        result = protocol._decode_payload(b"json obj data unvalid")

        self.assertIsNone(result)
        self.assertTrue(protocol._v35_query_fallback_needed)
        self.assertFalse(protocol._v35_query_fallback)
        self.assertEqual(protocol.dev_type, "v3.5")

    async def test_v35_status_retries_once_with_query_fallback(self):
        protocol = self._direct_protocol(3.5)
        protocol._v35_query_fallback_needed = True
        protocol.exchange = AsyncMock(
            side_effect=[None, {"dps": {"1": True}}]
        )

        status = await protocol.status()

        self.assertEqual(status, {"1": True})
        self.assertTrue(protocol._v35_query_fallback)
        self.assertFalse(protocol._v35_query_fallback_needed)
        self.assertEqual(protocol.exchange.await_count, 2)


if __name__ == "__main__":
    unittest.main()
