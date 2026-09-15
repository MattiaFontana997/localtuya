"""Exercise actual TCP framing, encryption and gateway routing on loopback.

The peer implements the 3.3 wire format independently of pytuya's codec.
These are protocol integration tests, not hardware compatibility claims.
"""
import asyncio
import json
import struct
import unittest
import zlib
from unittest.mock import AsyncMock, MagicMock, patch

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from custom_components.localtuya import pytuya, gateway_transport

KEY = b"0123456789abcdef"


def crypt(data, encrypt):
    context = Cipher(algorithms.AES(KEY), modes.ECB())
    if encrypt:
        size = 16 - len(data) % 16
        data += bytes([size]) * size
        worker = context.encryptor()
    else:
        worker = context.decryptor()
    result = worker.update(data) + worker.finalize()
    return result if encrypt else result[:-result[-1]]


def frame(seq, command, body):
    payload = struct.pack(">I", 0) + crypt(json.dumps(body).encode(), True)
    packet = struct.pack(">4I", 0x55AA, seq, command, len(payload) + 8) + payload
    return packet + struct.pack(">2I", zlib.crc32(packet) & 0xffffffff, 0xAA55)


class SocketIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tasks = []
        self.writers = []
        self.peers = []
        self.shared = None
        self.states = {"direct": {"1": True, "16": 215, "24": 203}}
        self.push_during_query = False
        self.drop_during_query = False
        self.push_cid = None
        self.server = await asyncio.start_server(self.accept, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    def accept(self, reader, writer):
        self.writers.append(writer)
        self.tasks.append(asyncio.create_task(self.serve(reader, writer)))

    async def serve(self, reader, writer):
        try:
            while True:
                header = await reader.readexactly(16)
                prefix, seq, command, length = struct.unpack(">4I", header)
                self.assertEqual(prefix, 0x55AA)
                rest = await reader.readexactly(length)
                self.assertEqual(struct.unpack(">I", rest[-8:-4])[0], zlib.crc32(header + rest[:-8]) & 0xffffffff)
                payload = rest[:-8]
                if payload.startswith(b"3.3"):
                    payload = payload[15:]
                body = json.loads(crypt(payload, False))
                if self.drop_during_query and command == 10:
                    writer.close()
                    return
                cid = body.get("cid", "direct")
                state = self.states.setdefault(cid, {"20": False})
                if command == 7:
                    state.update(body["dps"])
                response = {"dps": dict(state)}
                if cid != "direct":
                    response["cid"] = cid
                if self.push_during_query and command == 10:
                    writer.write(frame(0, 8, {"cid": self.push_cid or cid, "dps": {"25": 77}}))
                    await writer.drain()
                    await asyncio.sleep(0.01)
                packet = frame(seq, command, response)
                # Real TCP clients must tolerate arbitrary packet boundaries.
                writer.write(packet[:7])
                await writer.drain()
                await asyncio.sleep(0)
                writer.write(packet[7:])
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            writer.close()

    async def connect(self):
        peer = await pytuya.connect("127.0.0.1", "gateway", KEY.decode(), 3.3, False, port=self.port)
        self.peers.append(peer)
        return peer

    async def asyncTearDown(self):
        if self.shared:
            await self.shared.close()
        for peer in self.peers:
            await peer.close()
        self.server.close()
        await self.server.wait_closed()
        for writer in self.writers:
            writer.close()
            await writer.wait_closed()
        await asyncio.gather(*self.tasks)

    async def test_direct_thermostat_reads_and_changes_target(self):
        peer = await self.connect()
        async with asyncio.timeout(3):
            initial = dict(await peer.status())
            self.assertEqual(initial["24"], 203)
            await peer.set_dp(225, 16)
            self.assertEqual((await peer.status())["16"], 225)
            await peer.heartbeat()

    async def test_five_children_concurrent_commands_remain_isolated(self):
        parent = await self.connect()
        self.shared = gateway_transport.SharedGatewayTransport(
            None, (), parent, "gateway", gateway_transport._GatewayListener()
        )
        children = [self.shared.add_child(f"lamp-{n}", f"cid-{n}", MagicMock()) for n in range(5)]
        async with asyncio.timeout(5):
            for turn in range(10):
                await asyncio.gather(*(child.set_dp(turn * 10 + n, 22) for n, child in enumerate(children)))
                states = await asyncio.gather(*(child.status() for child in children))
                self.assertEqual([state["22"] for state in states], [turn * 10 + n for n in range(5)])
        self.assertEqual(len(self.writers), 1)

    async def test_push_during_query_is_not_lost_from_child_cache(self):
        parent = await self.connect()
        self.shared = gateway_transport.SharedGatewayTransport(
            None, (), parent, "gateway", gateway_transport._GatewayListener()
        )
        listener = MagicMock()
        child = self.shared.add_child("lamp", "cid-1", listener)
        self.push_during_query = True
        async with asyncio.timeout(3):
            await child.status()
        listener.status_updated.assert_called()
        self.assertEqual(child.dps_cache.get("25"), 77)

    async def test_socket_drop_fails_promptly_and_fresh_connection_recovers(self):
        peer = await self.connect()
        self.drop_during_query = True
        async with asyncio.timeout(2):
            with self.assertRaises(ConnectionError):
                await peer.status()
        self.drop_during_query = False
        replacement = await self.connect()
        async with asyncio.timeout(2):
            self.assertEqual((await replacement.status())["24"], 203)

    async def test_other_child_push_during_query_stays_isolated(self):
        parent = await self.connect()
        self.shared = gateway_transport.SharedGatewayTransport(
            None, (), parent, "gateway", gateway_transport._GatewayListener()
        )
        first = self.shared.add_child("lamp-1", "cid-1", MagicMock())
        second = self.shared.add_child("lamp-2", "cid-2", MagicMock())
        self.push_during_query = True
        self.push_cid = "cid-2"
        async with asyncio.timeout(3):
            await first.status()
        self.assertNotIn("25", first.dps_cache)
        self.assertEqual(second.dps_cache.get("25"), 77)

    async def test_connect_timeout_covers_socket_establishment(self):
        loop = asyncio.get_running_loop()
        async def stalled_connect(*args, **kwargs):
            await asyncio.Event().wait()
        async with asyncio.timeout(0.5):
            with patch.object(loop, "create_connection", new=AsyncMock(side_effect=stalled_connect)):
                with self.assertRaises(TimeoutError):
                    await pytuya.connect("127.0.0.1", "device", KEY.decode(), 3.3, False, timeout=0.01)
