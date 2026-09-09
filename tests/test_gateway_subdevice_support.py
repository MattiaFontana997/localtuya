"""Regression tests for Tuya gateway child-device routing."""

from __future__ import annotations

import asyncio
import json
import unittest

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

    async def test_v33_child_control_contains_cid(self):
        protocol = self._protocol(3.3)

        payload = protocol._generate_payload(
            pytuya.CONTROL,
            {"1": True},
        )
        body = json.loads(payload.payload.decode())

        self.assertEqual(body["cid"], "node-123")
        self.assertEqual(body["devId"], "child-device-id")
        self.assertEqual(body["dps"], {"1": True})

    async def test_v33_child_query_contains_cid(self):
        protocol = self._protocol(3.3)

        payload = protocol._generate_payload(pytuya.DP_QUERY)
        body = json.loads(payload.payload.decode())

        self.assertEqual(body["cid"], "node-123")
        self.assertEqual(body["gwId"], "gateway-device-id")
        self.assertEqual(body["devId"], "child-device-id")

    async def test_v35_child_control_preserves_cid_and_dps(self):
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

    async def test_v35_child_query_contains_nested_cid(self):
        protocol = self._protocol(3.5)

        payload = protocol._generate_payload(pytuya.DP_QUERY)
        body = json.loads(payload.payload.decode())

        self.assertEqual(body["cid"], "node-123")
        self.assertEqual(body["data"]["cid"], "node-123")
        self.assertEqual(body["data"]["ctype"], 0)


if __name__ == "__main__":
    unittest.main()
